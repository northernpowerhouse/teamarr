"""Stream classification for matching strategy selection.

Classifies streams into categories that determine which matching
strategy to use:
- TEAM_VS_TEAM: Standard team sports (NFL, NBA, Soccer, etc.)
- EVENT_CARD: Combat sports with event cards (UFC, Boxing)
- PLACEHOLDER: Filler streams with no event info (skip)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from re import Pattern

from teamarr.consumers.matching.normalizer import NormalizedStream, normalize_stream
from teamarr.utilities.constants import (
    EVENT_CARD_KEYWORDS,
    GAME_SEPARATORS,
    LEAGUE_HINT_PATTERNS,
    PLACEHOLDER_PATTERNS,
    SPORT_HINT_PATTERNS,
)

logger = logging.getLogger(__name__)


class StreamCategory(Enum):
    """Stream category for matching strategy selection."""

    TEAM_VS_TEAM = "team_vs_team"  # Standard team matchup (vs/@/at)
    EVENT_CARD = "event_card"  # Combat sports (UFC, Boxing)
    PLACEHOLDER = "placeholder"  # No event info, skip


@dataclass
class ClassifiedStream:
    """Result of stream classification with extracted components."""

    category: StreamCategory
    normalized: NormalizedStream

    # For TEAM_VS_TEAM: extracted team names
    team1: str | None = None
    team2: str | None = None
    separator_found: str | None = None

    # For EVENT_CARD: event hint (e.g., "UFC 315")
    event_hint: str | None = None

    # Detected league hint (for any category)
    league_hint: str | None = None

    # Detected sport hint (e.g., "Hockey", "Football")
    sport_hint: str | None = None

    # Track if custom regex was used
    custom_regex_used: bool = False


@dataclass
class CustomRegexConfig:
    """Configuration for custom regex team extraction."""

    teams_pattern: str | None = None
    teams_enabled: bool = False

    # Compiled pattern (cached)
    _compiled: Pattern | None = None

    def get_pattern(self) -> Pattern | None:
        """Get compiled regex pattern, compiling on first access."""
        if not self.teams_enabled or not self.teams_pattern:
            return None

        if self._compiled is None:
            try:
                self._compiled = re.compile(self.teams_pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning("[CLASSIFY] Invalid custom regex pattern: %s", e)
                return None

        return self._compiled


def extract_teams_with_custom_regex(
    text: str,
    config: CustomRegexConfig,
) -> tuple[str | None, str | None, bool]:
    """Extract team names using custom regex pattern.

    Args:
        text: Stream name (normalized)
        config: Custom regex configuration

    Returns:
        Tuple of (team1, team2, success)
    """
    pattern = config.get_pattern()
    if not pattern:
        return None, None, False

    match = pattern.search(text)
    if not match:
        return None, None, False

    # Try numbered groups first (group 1 and 2)
    groups = match.groups()
    if len(groups) >= 2:
        team1 = groups[0].strip() if groups[0] else None
        team2 = groups[1].strip() if groups[1] else None
        if team1 and team2:
            return team1, team2, True

    # Try named groups (?P<team1>...) and (?P<team2>...)
    try:
        team1 = match.group("team1")
        team2 = match.group("team2")
        if team1 and team2:
            return team1.strip(), team2.strip(), True
    except (IndexError, re.error):
        pass

    return None, None, False


# =============================================================================
# PLACEHOLDER DETECTION
# =============================================================================


def is_placeholder(text: str) -> bool:
    """Check if stream name matches placeholder patterns.

    Placeholders are filler streams with no real event info,
    like "ESPN+ 45" or "Coming Soon".

    Args:
        text: Normalized stream name

    Returns:
        True if stream is a placeholder
    """
    if not text:
        return True

    text_lower = text.lower().strip()

    # Check against placeholder patterns
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True

    # Additional check: very short names with just numbers
    if re.match(r"^[\d\s\-:]+$", text_lower):
        return True

    return False


# =============================================================================
# GAME SEPARATOR DETECTION
# =============================================================================


def find_game_separator(text: str) -> tuple[str | None, int]:
    """Find game separator in stream name.

    Args:
        text: Stream name (should be normalized)

    Returns:
        Tuple of (separator found, position) or (None, -1)
    """
    if not text:
        return None, -1

    text_lower = text.lower()

    for sep in GAME_SEPARATORS:
        pos = text_lower.find(sep.lower())
        if pos != -1:
            return sep, pos

    return None, -1


def extract_teams_from_separator(
    text: str, separator: str, sep_position: int
) -> tuple[str | None, str | None]:
    """Extract team names from a stream with a separator.

    Args:
        text: Stream name
        separator: The separator found (e.g., " vs ")
        sep_position: Position of separator in text

    Returns:
        Tuple of (team1, team2)
    """
    if sep_position < 0:
        return None, None

    team1 = text[:sep_position].strip()
    team2 = text[sep_position + len(separator) :].strip()

    # Clean up teams (remove DATE_MASK, TIME_MASK, trailing punctuation)
    team1 = _clean_team_name(team1)
    team2 = _clean_team_name(team2)

    # Validate: both teams should have substance
    if not team1 or len(team1) < 2:
        team1 = None
    if not team2 or len(team2) < 2:
        team2 = None

    return team1, team2


def _clean_team_name(name: str) -> str:
    """Clean extracted team name."""
    if not name:
        return ""

    # Remove datetime masks and trailing timezone remnants
    name = re.sub(r"\bDATE_MASK\b", "", name)
    name = re.sub(r"\bTIME_MASK\b", "", name)
    # After mask removal, clean up "@ ET", "@ EST", "@ PT", etc.
    name = re.sub(r"\s*@\s*[A-Z]{2,4}T?\s*$", "", name, flags=re.IGNORECASE)

    # Remove leading punctuation ONLY (not digits - team names like 49ers, 76ers start with numbers)
    # Strip whitespace, dashes, colons, periods, commas at the start
    name = re.sub(r"^[\s\-:.,]+", "", name)

    # Remove trailing punctuation (NOT digits - they could be team names like 49ers, 76ers)
    # Only strip trailing separators that shouldn't be part of team names
    name = re.sub(r"[\s\-:.,@]+$", "", name)

    # Remove channel numbers like "(1)" or "[2]"
    name = re.sub(r"\s*[\(\[]\d+[\)\]]\s*$", "", name)

    # Remove HD, SD, etc.
    name = re.sub(r"\s+\b(HD|SD|FHD|4K|UHD)\b\s*$", "", name, flags=re.IGNORECASE)

    # Strip leading channel numbers like "02 :", "15 :", "142 :" (from ESPN+ XX :)
    name = re.sub(r"^\d+\s*:\s*", "", name)

    # Strip numbered channel prefixes like "NFL Game Pass 03:", "ESPN+ 45:", "Sportsnet+ 04:"
    # Pattern: Words (may include +) followed by optional number, then colon
    # This handles "Name Number:" and "Name+ Number:" patterns at the start
    name = re.sub(r"^[A-Za-z][A-Za-z\s+]*\d*:\s*", "", name)

    # Strip round/competition indicators at end of team names
    # Common patterns in cup competitions, playoffs, etc.
    # - (Round 3), (Rd 3), (R3), (Rnd 3), (3rd Round), (Third Round)
    # - (Group A), (Grp A), (Group Stage)
    # - (Matchday 5), (MD 5), (MD5), (Week 10)
    # - (Leg 1), (1st Leg), (2nd Leg), (Leg One)
    # - (Final), (Semi-Final), (Quarter-Final), (QF), (SF), (Semi)
    # - (Playoffs), (Playoff), (Play-off)
    # - (Qualifying), (Qual), (Q1), (Q2)
    round_pattern = r"""
        \s*\(
        (?:
            (?:Round|Rd|Rnd|R)\s*\d+\w*  |  # Round 3, Rd 3, R3
            \d+(?:st|nd|rd|th)?\s*(?:Round|Rd|Leg)  |  # 3rd Round, 1st Leg
            (?:First|Second|Third|Fourth|Fifth)\s*(?:Round|Leg)  |  # Third Round
            (?:Group|Grp|Gr)\s*\w*  |  # Group A, Group Stage
            (?:Matchday|MD|Week|Wk)\s*\d*  |  # Matchday 5, MD5, Week 10
            (?:Leg|Game)\s*(?:One|Two|\d+)  |  # Leg 1, Leg One
            (?:Quarter|Semi|Half)?-?(?:Final|Finals)  |  # Final, Semi-Final
            (?:QF|SF|F)  |  # QF, SF, F
            (?:Play-?off|Play-?offs)  |  # Playoff, Play-off
            (?:Qualifying|Qual|Q)\d*  |  # Qualifying, Q1
            (?:Prelim|Preliminary)  |  # Preliminary
            (?:1H|2H|OT|ET)  |  # 1st half, overtime, extra time markers
            (?:Live|LIVE|Replay|Encore)  # Broadcast markers
        )
        \s*\)
    """
    name = re.sub(round_pattern, "", name, flags=re.IGNORECASE | re.VERBOSE)

    # Handle "|" separator - often used for show description before team names
    # "Manningcast | MNF with Peyton & Eli: Seahawks" → take part after last "|"
    # But only if there's no game separator after the "|" portion
    if "|" in name:
        # Check if the part after the last colon looks like a team name
        parts = name.split("|")
        last_part = parts[-1].strip()
        # If the last part after "|" has a colon with something after it, use that
        if ":" in last_part:
            after_colon = last_part.split(":")[-1].strip()
            if after_colon and len(after_colon) >= 3:
                name = after_colon

    # Strip show name prefixes that precede team names
    # Patterns like "MNF Playbook:", "NFL RedZone:", "Inside the NBA:"
    # Match pattern: "Word Word:" or "Word Word Word:" at the start
    # Must start with capital letter and contain only letters/spaces before colon
    # Apply repeatedly to handle nested prefixes like "Channel: Show: Team"
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r"^[A-Z][A-Za-z\s]+:\s*", "", name)

    return name.strip()


# =============================================================================
# LEAGUE HINT DETECTION
# =============================================================================


def detect_league_hint(text: str) -> str | None:
    """Detect league from stream name patterns.

    Examples:
        "NHL: Bruins vs Rangers" → "nhl"
        "EPL - Arsenal vs Chelsea" → "eng.1"
        "UFC 315: Main Card" → "ufc"

    Args:
        text: Stream name (should be normalized)

    Returns:
        League code if detected, None otherwise
    """
    if not text:
        return None

    text_lower = text.lower()

    for pattern, league_code in LEAGUE_HINT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return league_code

    return None


def detect_sport_hint(text: str) -> str | None:
    """Detect sport type from stream name.

    Unlike league hints which only match at start of string,
    sport hints can match anywhere (e.g., "Ice Hockey" in the middle).

    Examples:
        "US (BTN+) | Ice Hockey (W): Minnesota at Wisconsin" → "Hockey"
        "ESPN: NFL Sunday Football" → "Football"
        "Basketball: Lakers vs Celtics" → "Basketball"

    Args:
        text: Stream name (should be normalized)

    Returns:
        Sport name matching leagues.sport column if detected, None otherwise
    """
    if not text:
        return None

    text_lower = text.lower()

    for pattern, sport in SPORT_HINT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return sport

    return None


# =============================================================================
# EVENT CARD DETECTION
# =============================================================================


def is_event_card(text: str, league_event_type: str | None = None) -> bool:
    """Check if stream is an event card (UFC, Boxing).

    Args:
        text: Normalized stream name
        league_event_type: Optional event_type from leagues table

    Returns:
        True if stream is an event card
    """
    if not text:
        return False

    # If we know the league type, use that
    if league_event_type == "event_card":
        return True

    text_lower = text.lower()

    # Check for event card keywords
    for _league, keywords in EVENT_CARD_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True

    return False


def extract_event_card_hint(text: str) -> str | None:
    """Extract event card identifier (e.g., "UFC 315").

    Args:
        text: Stream name

    Returns:
        Event identifier if found, None otherwise
    """
    if not text:
        return None

    # UFC 315, UFC FN 123, etc.
    ufc_match = re.search(r"\b(ufc\s*(?:fn|fight\s*night)?\s*\d+)\b", text, re.IGNORECASE)
    if ufc_match:
        return ufc_match.group(1).upper().replace("  ", " ")

    # PFL 5, Bellator 300, etc.
    org_match = re.search(r"\b((?:pfl|bellator|one\s*fc)\s*\d+)\b", text, re.IGNORECASE)
    if org_match:
        return org_match.group(1).upper()

    # Boxing event names are less standardized - look for main event patterns
    if any(kw in text.lower() for kw in EVENT_CARD_KEYWORDS.get("boxing", [])):
        # Try to extract fighter names or event name
        # For now, just return a generic hint
        return "BOXING_EVENT"

    return None


# =============================================================================
# MAIN CLASSIFICATION
# =============================================================================


def classify_stream(
    stream_name: str,
    league_event_type: str | None = None,
    custom_regex: CustomRegexConfig | None = None,
) -> ClassifiedStream:
    """Classify a stream for matching strategy selection.

    Classification order:
    1. Normalize stream name
    2. Check for placeholder patterns → PLACEHOLDER
    3. Check for event card keywords/type → EVENT_CARD
    4. Try custom regex for team extraction (if configured) → TEAM_VS_TEAM
    5. Check for game separator (vs/@/at) → TEAM_VS_TEAM
    6. Default → PLACEHOLDER (can't classify)

    Args:
        stream_name: Raw stream name from M3U
        league_event_type: Optional event_type from leagues table
        custom_regex: Optional custom regex configuration for team extraction

    Returns:
        ClassifiedStream with category and extracted info
    """
    # Step 1: Normalize
    normalized = normalize_stream(stream_name)
    result: ClassifiedStream | None = None

    # Early exit for empty streams
    if not normalized.normalized:
        result = ClassifiedStream(
            category=StreamCategory.PLACEHOLDER,
            normalized=normalized,
        )
    else:
        text = normalized.normalized

        # Step 2: Check placeholder patterns
        if is_placeholder(text):
            result = ClassifiedStream(
                category=StreamCategory.PLACEHOLDER,
                normalized=normalized,
            )
        else:
            # Detect league and sport hints (useful for all categories)
            league_hint = detect_league_hint(text)
            sport_hint = detect_sport_hint(text)

            # Step 3: Check for event card
            if is_event_card(text, league_event_type):
                event_hint = extract_event_card_hint(text)
                result = ClassifiedStream(
                    category=StreamCategory.EVENT_CARD,
                    normalized=normalized,
                    event_hint=event_hint,
                    league_hint=league_hint,
                    sport_hint=sport_hint,
                )

            # Step 4: Try custom regex for team extraction (if configured)
            elif custom_regex and custom_regex.teams_enabled:
                team1, team2, success = extract_teams_with_custom_regex(text, custom_regex)
                if success:
                    result = ClassifiedStream(
                        category=StreamCategory.TEAM_VS_TEAM,
                        normalized=normalized,
                        team1=team1,
                        team2=team2,
                        separator_found="custom_regex",
                        league_hint=league_hint,
                        sport_hint=sport_hint,
                        custom_regex_used=True,
                    )

            # Step 5: Check for game separator (builtin fallback)
            if result is None:
                separator, sep_position = find_game_separator(text)
                if separator:
                    team1, team2 = extract_teams_from_separator(text, separator, sep_position)

                    # Only classify as TEAM_VS_TEAM if we got at least one team
                    if team1 or team2:
                        result = ClassifiedStream(
                            category=StreamCategory.TEAM_VS_TEAM,
                            normalized=normalized,
                            team1=team1,
                            team2=team2,
                            separator_found=separator,
                            league_hint=league_hint,
                            sport_hint=sport_hint,
                        )

            # Step 6: Default to placeholder if we can't classify
            if result is None:
                result = ClassifiedStream(
                    category=StreamCategory.PLACEHOLDER,
                    normalized=normalized,
                    league_hint=league_hint,
                    sport_hint=sport_hint,
                )

    logger.debug(
        "[CLASSIFY] '%s' -> %s (league=%s, sport=%s, teams=%s/%s)",
        stream_name[:50],
        result.category.value,
        result.league_hint,
        result.sport_hint,
        result.team1,
        result.team2,
    )

    return result


def classify_streams(
    stream_names: list[str],
    league_event_type: str | None = None,
    custom_regex: CustomRegexConfig | None = None,
) -> list[ClassifiedStream]:
    """Classify multiple streams.

    Args:
        stream_names: List of raw stream names
        league_event_type: Optional event_type from leagues table
        custom_regex: Optional custom regex configuration for team extraction

    Returns:
        List of ClassifiedStream objects
    """
    return [classify_stream(name, league_event_type, custom_regex) for name in stream_names]
