"""League configuration queries.

Single source of truth for league → provider routing.
The `leagues` table contains both API config and display data for explicitly
configured leagues (~30). Discovered leagues (~300) live in `league_cache`.

Note: LeagueMapping is defined in core.interfaces for layer separation.
This module uses it for database operations.
"""

import sqlite3

from teamarr.core import LeagueMapping


def get_league_id(conn: sqlite3.Connection, league_code: str) -> str:
    """Get the display league ID for a league.

    Returns league_id_alias if configured, otherwise returns league_code.
    This is the SINGLE SOURCE OF TRUTH for resolving league IDs.

    Args:
        conn: Database connection
        league_code: Raw league code (e.g., 'eng.1', 'college-football')

    Returns:
        Alias (e.g., 'epl', 'ncaaf') if configured, otherwise league_code
    """
    cursor = conn.execute(
        "SELECT league_id_alias FROM leagues WHERE league_code = ?",
        (league_code,),
    )
    row = cursor.fetchone()
    if row and row["league_id_alias"]:
        return row["league_id_alias"]
    return league_code


def get_league_mapping(
    conn: sqlite3.Connection, league_code: str, provider: str
) -> LeagueMapping | None:
    """Get mapping for a league from a specific provider.

    Args:
        conn: Database connection
        league_code: Canonical league code (e.g., 'nfl', 'ohl')
        provider: Provider name ('espn' or 'tsdb')

    Returns:
        LeagueMapping or None if not found/disabled
    """
    cursor = conn.execute(
        """
        SELECT league_code, provider, provider_league_id,
               provider_league_name, sport, display_name, logo_url
        FROM leagues
        WHERE league_code = ? AND provider = ? AND enabled = 1
        """,
        (league_code.lower(), provider),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return LeagueMapping(
        league_code=row["league_code"],
        provider=row["provider"],
        provider_league_id=row["provider_league_id"],
        provider_league_name=row["provider_league_name"],
        sport=row["sport"],
        display_name=row["display_name"],
        logo_url=row["logo_url"],
    )


def provider_supports_league(conn: sqlite3.Connection, league_code: str, provider: str) -> bool:
    """Check if a provider supports a league.

    Args:
        conn: Database connection
        league_code: Canonical league code
        provider: Provider name

    Returns:
        True if provider has enabled mapping for this league
    """
    cursor = conn.execute(
        """
        SELECT 1 FROM leagues
        WHERE league_code = ? AND provider = ? AND enabled = 1
        """,
        (league_code.lower(), provider),
    )
    return cursor.fetchone() is not None


def get_leagues_for_provider(conn: sqlite3.Connection, provider: str) -> list[LeagueMapping]:
    """Get all enabled leagues for a provider.

    Args:
        conn: Database connection
        provider: Provider name

    Returns:
        List of LeagueMapping for all enabled leagues
    """
    cursor = conn.execute(
        """
        SELECT league_code, provider, provider_league_id,
               provider_league_name, sport, display_name, logo_url
        FROM leagues
        WHERE provider = ? AND enabled = 1
        ORDER BY league_code
        """,
        (provider,),
    )
    return [
        LeagueMapping(
            league_code=row["league_code"],
            provider=row["provider"],
            provider_league_id=row["provider_league_id"],
            provider_league_name=row["provider_league_name"],
            sport=row["sport"],
            display_name=row["display_name"],
            logo_url=row["logo_url"],
        )
        for row in cursor.fetchall()
    ]
