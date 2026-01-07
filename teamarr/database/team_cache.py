"""Team cache database queries.

Simple queries for the team_cache table.
Used by providers to look up team names without going through consumers layer.
"""

from sqlite3 import Connection


def get_team_name_by_id(
    conn: Connection,
    provider_team_id: str,
    league: str,
    provider: str = "tsdb",
) -> str | None:
    """Get team name from provider team ID.

    Uses seeded/cached data instead of making API calls.
    This is critical for TSDB performance - avoids 2 API calls per lookup.

    Args:
        conn: Database connection
        provider_team_id: Team ID from the provider
        league: League slug to search in
        provider: Provider name (default 'tsdb')

    Returns:
        Team name if found, None otherwise
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT team_name FROM team_cache
        WHERE provider_team_id = ? AND league = ? AND provider = ?
        """,
        (provider_team_id, league, provider),
    )
    row = cursor.fetchone()
    return row["team_name"] if row else None
