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


def get_team_leagues_from_cache(
    conn: Connection,
    provider: str,
    provider_team_id: str,
    sport: str,
) -> list[str]:
    """Get all leagues a team appears in from the cache for a given sport.

    Args:
        conn: Database connection
        provider: Provider name (e.g., 'espn')
        provider_team_id: Provider's team ID
        sport: Sport name

    Returns:
        List of distinct league codes
    """
    cursor = conn.execute(
        "SELECT DISTINCT league FROM team_cache WHERE provider = ? AND provider_team_id = ? AND sport = ?",  # noqa: E501
        (provider, provider_team_id, sport),
    )
    return [row["league"] for row in cursor.fetchall()]


def search_teams(
    conn: Connection,
    query: str,
    league: str | None = None,
    sport: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search for teams in the cache by name.

    Matches against team_name (LIKE), team_abbrev (exact), and
    team_short_name (LIKE).

    Args:
        conn: Database connection
        query: Search query (case-insensitive)
        league: Optional league filter
        sport: Optional sport filter
        limit: Max results (default 50)

    Returns:
        List of matching team dicts
    """
    q_lower = query.lower().strip()

    sql = """
        SELECT team_name, team_abbrev, team_short_name, provider,
               provider_team_id, league, sport, logo_url
        FROM team_cache
        WHERE (LOWER(team_name) LIKE ?
               OR LOWER(team_abbrev) = ?
               OR LOWER(team_short_name) LIKE ?)
    """
    params: list = [f"%{q_lower}%", q_lower, f"%{q_lower}%"]

    if league:
        sql += " AND league = ?"
        params.append(league)
    if sport:
        sql += " AND sport = ?"
        params.append(sport)

    sql += " ORDER BY team_name LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "name": row["team_name"],
            "abbrev": row["team_abbrev"],
            "short_name": row["team_short_name"],
            "provider": row["provider"],
            "team_id": row["provider_team_id"],
            "league": row["league"],
            "sport": row["sport"],
            "logo_url": row["logo_url"],
        }
        for row in rows
    ]
