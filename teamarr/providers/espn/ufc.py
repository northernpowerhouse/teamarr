"""UFC event parsing for ESPN provider.

Extracted as a mixin to keep provider.py focused on core sports.
"""

import logging
from datetime import date

from teamarr.core import Event, EventStatus, Team
from teamarr.utilities.tz import to_user_tz

logger = logging.getLogger(__name__)


class UFCParserMixin:
    """Mixin providing UFC-specific parsing methods.

    Requires:
        - self._client: ESPNClient instance
        - self.name: Provider name ('espn')
        - self._parse_datetime(date_str): Parse datetime from string
    """

    def _get_ufc_events(self, target_date: date) -> list[Event]:
        """Fetch and parse UFC events for a specific date.

        Uses scoreboard endpoint (correct times) for current/upcoming events.
        Falls back to app API for events not on scoreboard.
        """
        events = []

        # Try scoreboard first - has correct segment times
        scoreboard_data = self._client.get_ufc_scoreboard()
        if scoreboard_data:
            scoreboard_events = scoreboard_data.get("events", [])
            for event_data in scoreboard_events:
                event = self._parse_ufc_event(event_data)
                if event:
                    local_date = to_user_tz(event.start_time).date()
                    if local_date == target_date:
                        events.append(event)
                        logger.debug(
                            "[ESPN_UFC] Using scoreboard data for %s (correct times)",
                            event.name,
                        )

        # If no events from scoreboard, try app API (times may be 3h late)
        if not events:
            data = self._client.get_ufc_events()
            if data:
                try:
                    ufc_events = data["sports"][0]["leagues"][0]["events"]
                    for event_data in ufc_events:
                        event = self._parse_ufc_event(event_data)
                        if event:
                            local_date = to_user_tz(event.start_time).date()
                            if local_date == target_date:
                                events.append(event)
                                logger.warning(
                                    "[ESPN_UFC] Using app API for %s (times may be inaccurate)",
                                    event.name,
                                )
                except (KeyError, IndexError):
                    logger.warning("[ESPN_UFC] Unexpected events response structure")

        return events

    def _parse_ufc_event(self, data: dict) -> Event | None:
        """Parse UFC fight card into Event.

        Maps the main event fighters as home_team/away_team for compatibility.
        Extracts exact segment times from ESPN bout-level data:
        - 3 distinct times: early_prelims, prelims, main_card (PPV events)
        - 2 distinct times: prelims, main_card (Fight Night events)
        - 1 time: main_card only
        """
        try:
            event_id = str(data.get("id", ""))
            if not event_id:
                return None

            competitions = data.get("competitions", [])
            if not competitions:
                return None

            # Group bouts by start time to derive segments
            # ESPN provides exact segment times via bout-level date fields
            bout_times: set[str] = set()
            for comp in competitions:
                if "date" in comp:
                    bout_times.add(comp["date"])

            if not bout_times:
                return None

            # Sort times chronologically to determine segments
            sorted_times = sorted(bout_times)

            # Build segment_times dict based on number of distinct times
            segment_times: dict[str, any] = {}
            if len(sorted_times) == 3:
                # PPV format: Early Prelims, Prelims, Main Card
                segment_times["early_prelims"] = self._parse_datetime(sorted_times[0])
                segment_times["prelims"] = self._parse_datetime(sorted_times[1])
                segment_times["main_card"] = self._parse_datetime(sorted_times[2])
            elif len(sorted_times) == 2:
                # Fight Night format: Prelims, Main Card
                segment_times["prelims"] = self._parse_datetime(sorted_times[0])
                segment_times["main_card"] = self._parse_datetime(sorted_times[1])
            else:
                # Single segment: Main Card only
                segment_times["main_card"] = self._parse_datetime(sorted_times[0])

            # Remove any None values (failed datetime parsing)
            segment_times = {k: v for k, v in segment_times.items() if v is not None}

            # Event start time is earliest segment
            start_time = min(segment_times.values()) if segment_times else None
            if not start_time:
                return None

            # Main card start for backwards compatibility
            main_card_start = segment_times.get("main_card")

            # Find the main event (first bout at main card time)
            main_card_time_str = sorted_times[-1]  # Latest time = main card
            main_event = next(
                (c for c in competitions if c.get("date") == main_card_time_str),
                competitions[0],
            )

            # Extract fighters as "teams"
            competitors = main_event.get("competitors", [])
            if len(competitors) < 2:
                return None

            fighter1 = self._parse_fighter_as_team(competitors[0])
            fighter2 = self._parse_fighter_as_team(competitors[1])

            # Parse status from main event
            status = self._parse_ufc_status(main_event.get("status", {}))

            logger.debug(
                "[ESPN_UFC] Event %s segments: %s",
                event_id,
                {k: v.isoformat() for k, v in segment_times.items()},
            )

            return Event(
                id=event_id,
                provider=self.name,
                name=data.get("name", ""),
                short_name=f"{fighter1.short_name} vs {fighter2.short_name}",
                start_time=start_time,
                home_team=fighter1,
                away_team=fighter2,
                status=status,
                league="ufc",
                sport="mma",  # Lowercase code; display name from sports table
                main_card_start=main_card_start,
                segment_times=segment_times,
            )
        except Exception as e:
            logger.warning("[ESPN_UFC] Failed to parse event %s: %s", data.get('id', 'unknown'), e)
            return None

    def _parse_fighter_as_team(self, competitor: dict) -> Team:
        """Convert UFC fighter to Team dataclass for compatibility."""
        athlete = competitor.get("athlete", {})

        # Get headshot URL
        headshots = athlete.get("headshots", {})
        logo_url = None
        if headshots:
            # Prefer full size, fallback to any available
            logo_url = headshots.get("full", {}).get("href")
            if not logo_url:
                for size in ["xlarge", "large", "medium"]:
                    if size in headshots:
                        logo_url = headshots[size].get("href")
                        break

        short_name = athlete.get("shortName", "")

        return Team(
            id=str(athlete.get("id", "")),
            provider=self.name,
            name=athlete.get("displayName", ""),
            short_name=short_name,
            abbreviation=short_name.replace(".", "").replace(" ", ""),
            league="ufc",
            sport="mma",  # Lowercase code; display name from sports table
            logo_url=logo_url,
            color=None,
        )

    def _parse_ufc_status(self, status_data: dict) -> EventStatus:
        """Parse UFC event status."""
        state_map = {
            "pre": "scheduled",
            "in": "live",
            "post": "final",
        }
        state = status_data.get("state", "pre")
        mapped_state = state_map.get(state, "scheduled")

        return EventStatus(
            state=mapped_state,
            detail=status_data.get("description"),
            period=None,
            clock=None,
        )
