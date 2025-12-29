"""Multi-league stream matcher.

Uses Events → Streams approach:
1. Fetch all events from configured leagues (parallel with ThreadPoolExecutor)
2. Generate search patterns from event data (team names, abbreviations)
3. For each stream, find events whose patterns appear in the stream name

This is more robust than parsing stream names because:
- We know exact team names/abbreviations from the provider
- Don't rely on parser correctly extracting from messy stream names
- Uses fuzzy matching for better tolerance of name variations
- Supports user-defined aliases for edge cases
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from teamarr.core import Event
from teamarr.services import SportsDataService
from teamarr.utilities.fuzzy_match import FuzzyMatcher, get_matcher
from teamarr.utilities.sports import get_sport_duration

# Number of parallel workers for event fetching
MAX_WORKERS = 100

logger = logging.getLogger(__name__)

# Leagues that only have ONE event per day
# For these, if stream contains the league keyword, match to the day's event
SINGLE_EVENT_LEAGUES = {
    "ufc": ["ufc", "fight night"],  # Keywords to look for
}


@dataclass
class StreamMatchResult:
    """Result of matching a single stream."""

    stream_name: str

    # Match outcome
    matched: bool
    event: Event | None = None
    league: str | None = None

    # Inclusion decision
    included: bool = False
    exclusion_reason: str | None = None

    # Exception handling
    exception_keyword: str | None = None

    @property
    def is_exception(self) -> bool:
        return self.exception_keyword is not None


@dataclass
class BatchMatchResult:
    """Result of matching a batch of streams."""

    results: list[StreamMatchResult]
    target_date: date
    leagues_searched: list[str]
    include_leagues: list[str]
    events_found: int

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def matched_count(self) -> int:
        return sum(1 for r in self.results if r.matched)

    @property
    def included_count(self) -> int:
        return sum(1 for r in self.results if r.included)

    @property
    def excluded_count(self) -> int:
        return sum(1 for r in self.results if r.matched and not r.included)

    @property
    def unmatched_count(self) -> int:
        return sum(1 for r in self.results if not r.matched and not r.is_exception)

    @property
    def exception_count(self) -> int:
        return sum(1 for r in self.results if r.is_exception)

    @property
    def match_rate(self) -> float:
        non_exception = self.total - self.exception_count
        if non_exception == 0:
            return 0.0
        return self.matched_count / non_exception


@dataclass
class EventPatterns:
    """Search patterns generated from an event."""

    event: Event
    league: str
    # Patterns to find BOTH of (for team_vs_team)
    home_patterns: list[str]
    away_patterns: list[str]
    # Patterns to find ANY of (for event name)
    event_patterns: list[str]


class MultiLeagueMatcher:
    """Matches streams to events using Events → Streams approach.

    Supports user-defined team aliases for edge cases where automatic
    matching fails.
    """

    def __init__(
        self,
        service: SportsDataService,
        search_leagues: list[str],
        include_leagues: list[str] | None = None,
        exception_keywords: list[str] | None = None,
        fuzzy_matcher: FuzzyMatcher | None = None,
        get_connection: Callable[[], Any] | None = None,
        include_final_events: bool = False,
        sport_durations: dict[str, float] | None = None,
    ):
        self._service = service
        self._search_leagues = search_leagues
        self._include_leagues = set(include_leagues) if include_leagues else None
        self._exception_keywords = [kw.lower() for kw in (exception_keywords or [])]
        self._fuzzy = fuzzy_matcher or get_matcher()
        self._get_connection = get_connection
        self._include_final_events = include_final_events
        self._sport_durations = sport_durations or {}

        # Built during match_all
        self._event_patterns: list[EventPatterns] = []
        self._patterns_date: date | None = None

        # Alias cache per league (loaded once)
        self._aliases: dict[str, dict[str, tuple[str, str]]] | None = None

    def match_all(self, stream_names: list[str], target_date: date) -> BatchMatchResult:
        """Match all streams against events from configured leagues."""
        # Build event patterns for target date
        self._build_event_patterns(target_date)

        # Match each stream
        results = [self._match_stream(name) for name in stream_names]

        return BatchMatchResult(
            results=results,
            target_date=target_date,
            leagues_searched=self._search_leagues,
            include_leagues=(
                list(self._include_leagues) if self._include_leagues else self._search_leagues
            ),
            events_found=len(self._event_patterns),
        )

    def _build_event_patterns(self, target_date: date) -> None:
        """Build search patterns from all events (parallel league fetching)."""
        if self._patterns_date == target_date:
            return

        self._event_patterns = []

        if not self._search_leagues:
            self._patterns_date = target_date
            return

        num_workers = min(MAX_WORKERS, len(self._search_leagues))

        def fetch_league_events(league: str) -> tuple[str, list[Event]]:
            """Fetch events for a single league (for parallel execution)."""
            try:
                events = self._service.get_events(league, target_date)
                return (league, events)
            except Exception as e:
                logger.warning(f"Failed to fetch events for {league}: {e}")
                return (league, [])

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(fetch_league_events, league): league
                for league in self._search_leagues
            }

            for future in as_completed(futures):
                try:
                    league, events = future.result()
                    for event in events:
                        # Filter final events (matching V1 logic)
                        if self._should_skip_final_event(event, target_date):
                            continue
                        patterns = self._generate_patterns(event, league)
                        self._event_patterns.append(patterns)
                except Exception as e:
                    league = futures[future]
                    logger.warning(f"Failed to fetch events for {league}: {e}")

        self._patterns_date = target_date

    def _should_skip_final_event(self, event: Event, target_date: date) -> bool:
        """Check if a final event should be skipped.

        Matches V1 logic:
        - Past day completed events: ALWAYS excluded
        - Today's completed events: honor include_final_events setting

        Args:
            event: Event to check
            target_date: The date we're matching for

        Returns:
            True if event should be skipped, False if it should be included
        """
        # Only filter if event is final
        if event.status.state != "final":
            return False

        # Calculate estimated end time
        duration = get_sport_duration(event.sport, self._sport_durations, 3.0)
        event_end = event.start_time + timedelta(hours=duration)

        # Check if event has actually ended
        now = datetime.now(event.start_time.tzinfo) if event.start_time.tzinfo else datetime.now()
        if event_end >= now:
            # Event hasn't ended yet (still in progress), include it
            return False

        # Event is final AND has ended
        event_day = event.start_time.date()
        today = target_date

        if event_day < today:
            # Past day completed event - always skip
            return True
        elif event_day == today and not self._include_final_events:
            # Today's final, but include_final_events is False - skip
            return True

        # Today's final with include_final_events=True - include it
        return False

    def _generate_patterns(self, event: Event, league: str) -> EventPatterns:
        """Generate search patterns from an event using fuzzy matcher."""
        # Use fuzzy matcher to generate patterns (includes mascot stripping)
        home_patterns = self._fuzzy.generate_team_patterns(event.home_team)
        away_patterns = self._fuzzy.generate_team_patterns(event.away_team)

        # Event name patterns
        event_patterns = self._unique_patterns(
            [
                event.name,
                event.short_name,
            ]
        )

        return EventPatterns(
            event=event,
            league=league,
            home_patterns=home_patterns,
            away_patterns=away_patterns,
            event_patterns=event_patterns,
        )

    def _unique_patterns(self, values: list[str]) -> list[str]:
        """Normalize and dedupe patterns."""
        seen = set()
        result = []
        for v in values:
            if v:
                lower = v.lower()
                if lower not in seen and len(lower) >= 2:
                    seen.add(lower)
                    result.append(lower)
        return result

    def _match_stream(self, stream_name: str) -> StreamMatchResult:
        """Match a stream against all event patterns."""
        stream_lower = stream_name.lower()

        # Check for exception keyword
        for keyword in self._exception_keywords:
            if keyword in stream_lower:
                return StreamMatchResult(
                    stream_name=stream_name,
                    matched=False,
                    exception_keyword=keyword,
                    exclusion_reason="exception",
                )

        # Find matching event
        event, league = self._find_matching_event(stream_lower)

        if not event:
            return StreamMatchResult(
                stream_name=stream_name,
                matched=False,
                exclusion_reason="unmatched",
            )

        # Check whitelist
        included = self._is_league_included(league)

        return StreamMatchResult(
            stream_name=stream_name,
            matched=True,
            event=event,
            league=league,
            included=included,
            exclusion_reason=None if included else "league_not_in_whitelist",
        )

    def _load_aliases(self) -> None:
        """Load user-defined aliases for all search leagues."""
        if self._aliases is not None:
            return

        self._aliases = {}

        if not self._get_connection:
            return

        try:
            from teamarr.database.aliases import list_aliases

            with self._get_connection() as conn:
                for league in self._search_leagues:
                    aliases = list_aliases(conn, league=league)
                    league_aliases = {}
                    for alias in aliases:
                        league_aliases[alias.alias.lower()] = (alias.team_id, alias.team_name)
                    if league_aliases:
                        self._aliases[league] = league_aliases

            total = sum(len(a) for a in self._aliases.values())
            if total:
                logger.debug(f"Loaded {total} aliases for {len(self._aliases)} leagues")
        except Exception as e:
            logger.warning(f"Failed to load aliases: {e}")
            self._aliases = {}

    def _find_alias_team_ids(self, stream_lower: str, league: str) -> set[str]:
        """Find team IDs from aliases that appear in stream for a specific league."""
        self._load_aliases()

        if league not in self._aliases:
            return set()

        found_team_ids = set()
        for alias_text, (team_id, team_name) in self._aliases[league].items():
            if f" {alias_text} " in f" {stream_lower} ":
                found_team_ids.add(team_id)
                logger.debug(f"Alias match: '{alias_text}' -> {team_name} ({team_id})")

        return found_team_ids

    def _find_matching_event(self, stream_lower: str) -> tuple[Event | None, str | None]:
        """Find event that matches the stream name.

        Matching passes (in priority order):
        1. Alias-based: Both teams found via user-defined aliases
        2. Both teams: Both home and away team patterns match
        3. Single-event leagues: UFC keyword matching (only one event per day)

        NOTE: Event name-only matching is intentionally disabled.
        It caused false positives (e.g., "Chicago" in event name matching
        unrelated "Chicago Blackhawks" stream).
        """
        # Expand abbreviations for matching (e.g., "UFC FN" → "UFC Fight Night")
        stream_expanded = self._fuzzy._expand_abbreviations(stream_lower)

        # First pass: try alias-based matching (highest priority)
        self._load_aliases()
        if self._aliases:
            for ep in self._event_patterns:
                alias_team_ids = self._find_alias_team_ids(stream_expanded, ep.league)
                if not alias_team_ids:
                    continue

                home_id = ep.event.home_team.id
                away_id = ep.event.away_team.id

                home_alias = home_id in alias_team_ids
                away_alias = away_id in alias_team_ids

                # Both teams via aliases
                if home_alias and away_alias:
                    return ep.event, ep.league

                # One team via alias, other via patterns
                if home_alias:
                    away_match = self._fuzzy.matches_any(ep.away_patterns, stream_expanded)
                    if away_match.matched:
                        return ep.event, ep.league

                if away_alias:
                    home_match = self._fuzzy.matches_any(ep.home_patterns, stream_expanded)
                    if home_match.matched:
                        return ep.event, ep.league

        # Second pass: both teams must match via fuzzy matching
        for ep in self._event_patterns:
            home_match = self._fuzzy.matches_any(ep.home_patterns, stream_expanded)
            away_match = self._fuzzy.matches_any(ep.away_patterns, stream_expanded)

            if home_match.matched and away_match.matched:
                return ep.event, ep.league

        # Third pass: single-event leagues (e.g., UFC)
        # These leagues only have ONE event per day, so keyword matching is sufficient
        match = self._match_single_event_league(stream_expanded)
        if match:
            return match

        return None, None

    def _match_single_event_league(
        self, stream_expanded: str
    ) -> tuple[Event | None, str | None] | None:
        """Match stream to single-event leagues (e.g., UFC).

        For leagues that only have ONE event per day, if the stream contains
        league-specific keywords, we can match it directly without needing
        team/fighter names.
        """
        for league, keywords in SINGLE_EVENT_LEAGUES.items():
            # Check if stream contains any of the league's keywords
            if not any(kw in stream_expanded for kw in keywords):
                continue

            # Find the single event for this league on the target date
            league_events = [ep for ep in self._event_patterns if ep.league == league]

            # Only match if there's exactly one event (the premise of single-event leagues)
            if len(league_events) == 1:
                return league_events[0].event, league

        return None

    def _is_league_included(self, league: str) -> bool:
        """Check if league is in the include whitelist."""
        if self._include_leagues is None:
            return True
        return league in self._include_leagues
