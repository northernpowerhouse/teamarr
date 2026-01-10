"""ESPN API HTTP client.

Handles raw HTTP requests to ESPN endpoints.
No data transformation - just fetch and return JSON.
"""

import logging
import ssl
import threading
import time

import httpx

logger = logging.getLogger(__name__)

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE_URL = "http://sports.core.api.espn.com/v2/sports"

# UFC uses different API endpoints
ESPN_UFC_EVENTS_URL = "https://api-app.espn.com/v1/sports/mma/ufc/events"
ESPN_UFC_ATHLETE_URL = "https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc/athletes"

COLLEGE_SCOREBOARD_GROUPS = {
    "mens-college-basketball": "50",
    "womens-college-basketball": "50",
    # Note: college-football omitted to return both FBS + FCS games
    # Note: mens-college-hockey does NOT need groups param
}

# Rate limiting defaults
DEFAULT_REQUESTS_PER_SECOND = 10.0  # Max sustained request rate
DEFAULT_BURST_SIZE = 20  # Allow burst of this many requests


class RateLimiter:
    """Token bucket rate limiter for API requests.

    Allows bursts up to bucket_size, then limits to rate requests/second.
    Thread-safe for concurrent use.
    """

    def __init__(self, rate: float = DEFAULT_REQUESTS_PER_SECOND, bucket_size: int = DEFAULT_BURST_SIZE):
        self._rate = rate
        self._bucket_size = bucket_size
        self._tokens = float(bucket_size)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available."""
        with self._lock:
            now = time.monotonic()
            # Replenish tokens based on time elapsed
            elapsed = now - self._last_update
            self._tokens = min(self._bucket_size, self._tokens + elapsed * self._rate)
            self._last_update = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # Need to wait for token
            wait_time = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0

        # Wait outside the lock
        time.sleep(wait_time)


class ESPNClient:
    """Low-level ESPN API client with rate limiting."""

    def __init__(
        self,
        timeout: float = 10.0,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND,
        burst_size: int = DEFAULT_BURST_SIZE,
    ):
        self._timeout = timeout
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()
        self._rate_limiter = RateLimiter(rate=requests_per_second, bucket_size=burst_size)

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            with self._lock:
                # Double-check after acquiring lock
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=self._timeout,
                        # Reduced from 100 to 50 to prevent overwhelming ESPN
                        limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
                    )
        return self._client

    def _is_ssl_error(self, error: Exception) -> bool:
        """Check if an error is SSL-related."""
        # Check for ssl.SSLError directly
        if isinstance(error, ssl.SSLError):
            return True
        # Check error message for SSL indicators
        error_str = str(error).lower()
        return "ssl" in error_str or "eof occurred" in error_str

    def _request(self, url: str, params: dict | None = None) -> dict | None:
        """Make HTTP request with retry logic and rate limiting."""
        for attempt in range(self._retry_count):
            try:
                # Apply rate limiting before each request
                self._rate_limiter.acquire()

                client = self._get_client()
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {url}")
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                return None
            except (httpx.RequestError, RuntimeError, OSError) as e:
                # RuntimeError: "Cannot send a request, as the client has been closed"
                # OSError: "Bad file descriptor" from stale connections
                # ssl.SSLError: SSL connection errors (subclass of OSError)
                logger.warning(f"Request failed for {url}: {e}")

                # Reset connection pool on SSL errors to get fresh connections
                if self._is_ssl_error(e):
                    logger.info("SSL error detected, resetting connection pool")
                    self._reset_client()

                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                return None

        return None

    def _reset_client(self) -> None:
        """Reset the HTTP client to clear stale connections."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

    def get_sport_league(
        self, league: str, override: tuple[str, str] | None = None
    ) -> tuple[str, str]:
        """Convert canonical league to ESPN sport/league pair.

        Args:
            league: Canonical league code (e.g., 'nfl', 'nba')
            override: (sport, league) tuple from database config (required for non-soccer)

        Returns:
            (sport, espn_league) tuple for API path construction
        """
        # Database config is the source of truth
        if override:
            return override
        # Soccer leagues use dot notation - can infer sport
        if "." in league:
            return ("soccer", league)
        # No config provided - log warning and return league as-is
        logger.warning(f"No database config for league '{league}' - add to leagues table")
        return ("unknown", league)

    def get_scoreboard(
        self,
        league: str,
        date_str: str,
        sport_league: tuple[str, str] | None = None,
    ) -> dict | None:
        """Fetch scoreboard for a league on a given date.

        Args:
            league: Canonical league code (e.g., 'nfl', 'nba')
            date_str: Date in YYYYMMDD format
            sport_league: Optional (sport, league) tuple from database config

        Returns:
            Raw ESPN response or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/scoreboard"
        params = {"dates": date_str}

        if league in COLLEGE_SCOREBOARD_GROUPS:
            params["groups"] = COLLEGE_SCOREBOARD_GROUPS[league]

        return self._request(url, params)

    def get_league_info(
        self,
        league: str,
        sport_league: tuple[str, str] | None = None,
    ) -> dict | None:
        """Fetch league metadata including logo from scoreboard endpoint.

        Args:
            league: Canonical league code (e.g., 'eng.fa', 'uefa.champions')
            sport_league: Optional (sport, league) tuple

        Returns:
            Dict with name, logo_url, abbreviation or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/scoreboard"

        data = self._request(url)
        if not data:
            return None

        leagues = data.get("leagues", [])
        if not leagues:
            return None

        league_data = leagues[0]
        logo_url = None

        # Extract logo - prefer default, fallback to first
        logos = league_data.get("logos", [])
        for logo in logos:
            rel = logo.get("rel", [])
            if "default" in rel:
                logo_url = logo.get("href")
                break
        if not logo_url and logos:
            logo_url = logos[0].get("href")

        return {
            "name": league_data.get("name"),
            "abbreviation": league_data.get("abbreviation"),
            "logo_url": logo_url,
            "id": league_data.get("id"),
        }

    def get_team_schedule(
        self,
        league: str,
        team_id: str,
        sport_league: tuple[str, str] | None = None,
    ) -> dict | None:
        """Fetch schedule for a specific team.

        Args:
            league: Canonical league code
            team_id: ESPN team ID
            sport_league: Optional (sport, league) tuple from database config

        Returns:
            Raw ESPN response or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/teams/{team_id}/schedule"
        return self._request(url)

    def get_team(
        self,
        league: str,
        team_id: str,
        sport_league: tuple[str, str] | None = None,
    ) -> dict | None:
        """Fetch team information.

        Args:
            league: Canonical league code
            team_id: ESPN team ID
            sport_league: Optional (sport, league) tuple from database config

        Returns:
            Raw ESPN response or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/teams/{team_id}"
        return self._request(url)

    def get_event(
        self,
        league: str,
        event_id: str,
        sport_league: tuple[str, str] | None = None,
    ) -> dict | None:
        """Fetch a single event by ID.

        Args:
            league: Canonical league code
            event_id: ESPN event ID
            sport_league: Optional (sport, league) tuple from database config

        Returns:
            Raw ESPN response or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/summary"
        return self._request(url, {"event": event_id})

    def get_teams(self, league: str, sport_league: tuple[str, str] | None = None) -> dict | None:
        """Fetch all teams for a league.

        Args:
            league: Canonical league code
            sport_league: Optional (sport, league) tuple from database config

        Returns:
            Raw ESPN response with teams list or None on error
        """
        sport, espn_league = self.get_sport_league(league, sport_league)
        url = f"{ESPN_BASE_URL}/{sport}/{espn_league}/teams"
        return self._request(url, {"limit": 1000})

    # UFC-specific endpoints

    def get_ufc_events(self) -> dict | None:
        """Fetch all UFC events from the app API.

        Returns:
            Raw ESPN response with events list or None on error
        """
        return self._request(ESPN_UFC_EVENTS_URL)

    def get_fighter(self, fighter_id: str) -> dict | None:
        """Fetch UFC fighter profile.

        Args:
            fighter_id: ESPN fighter/athlete ID

        Returns:
            Raw ESPN response or None on error
        """
        url = f"{ESPN_UFC_ATHLETE_URL}/{fighter_id}"
        return self._request(url)

    def get_fighter_record(self, fighter_id: str) -> dict | None:
        """Fetch UFC fighter record (W-L-D with breakdown).

        Args:
            fighter_id: ESPN fighter/athlete ID

        Returns:
            Raw ESPN response with record data or None on error
        """
        url = f"{ESPN_UFC_ATHLETE_URL}/{fighter_id}/records"
        return self._request(url)

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
