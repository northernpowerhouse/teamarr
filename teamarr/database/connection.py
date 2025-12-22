"""Database connection management.

Simple SQLite connection handling with schema initialization.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "teamarr.db"

# Schema file location
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Get a database connection.

    Args:
        db_path: Path to database file. Uses DEFAULT_DB_PATH if not specified.

    Returns:
        SQLite connection with row factory set to sqlite3.Row
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections.

    Usage:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM teams")
            teams = cursor.fetchall()
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database with schema.

    Creates tables if they don't exist. Safe to call multiple times.
    Also seeds TSDB cache from distributed seed file if needed.

    Args:
        db_path: Path to database file. Uses DEFAULT_DB_PATH if not specified.
    """
    schema_sql = SCHEMA_PATH.read_text()

    with get_db(db_path) as conn:
        conn.executescript(schema_sql)
        # Run migrations for existing databases
        _run_migrations(conn)
        # Seed TSDB cache if empty or incomplete
        _seed_tsdb_cache_if_needed(conn)


def _seed_tsdb_cache_if_needed(conn: sqlite3.Connection) -> None:
    """Seed TSDB cache from distributed seed file if needed."""
    from teamarr.database.seed import seed_if_needed

    result = seed_if_needed(conn)
    if result and result.get("seeded"):
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Seeded TSDB cache: {result.get('teams_added', 0)} teams, "
            f"{result.get('leagues_added', 0)} leagues"
        )


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run database migrations for existing databases.

    Uses schema_version in settings table to track applied migrations.
    Safe to call multiple times - checks version before running.

    Schema versions:
    - 2: Initial V2 schema
    - 3: Teams consolidated (league -> primary_league + leagues array)
    """
    import logging

    logger = logging.getLogger(__name__)

    # Get current schema version
    try:
        row = conn.execute("SELECT schema_version FROM settings WHERE id = 1").fetchone()
        current_version = row["schema_version"] if row else 2
    except Exception:
        current_version = 2

    # Migration: Add description_template to templates table (pre-versioning)
    _add_column_if_not_exists(
        conn, "templates", "description_template", "TEXT DEFAULT '{matchup} | {venue_full}'"
    )

    # Migration: Add tsdb_api_key to settings table (pre-versioning)
    _add_column_if_not_exists(conn, "settings", "tsdb_api_key", "TEXT")

    # Version 3: teams.league (TEXT) -> teams.primary_league + teams.leagues (JSON array)
    if current_version < 3:
        if _migrate_teams_to_leagues_array(conn):
            conn.execute("UPDATE settings SET schema_version = 3 WHERE id = 1")
            logger.info("Schema upgraded to version 3")
            current_version = 3


def _migrate_teams_to_leagues_array(conn: sqlite3.Connection) -> bool:
    """Migrate teams table from single league to leagues JSON array.

    Consolidates teams by (provider, provider_team_id, sport) with all
    their leagues merged into a JSON array.

    Returns:
        True if migration was performed, False if already migrated
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    # Check if table has old 'league' column
    cursor = conn.execute("PRAGMA table_info(teams)")
    columns = {row["name"] for row in cursor.fetchall()}

    if "league" not in columns or "leagues" in columns:
        # Already migrated or fresh database
        return False

    logger.info("Migrating teams table: league -> leagues array")

    # Get all existing teams grouped by (provider, provider_team_id, sport)
    cursor = conn.execute("""
        SELECT provider, provider_team_id, sport,
               GROUP_CONCAT(league) as leagues_concat,
               team_name, team_abbrev, team_logo_url, team_color,
               channel_id, channel_logo_url, template_id, active,
               MIN(created_at) as created_at,
               MAX(updated_at) as updated_at
        FROM teams
        GROUP BY provider, provider_team_id, sport
    """)
    rows = cursor.fetchall()

    # Create new table with leagues array
    conn.execute("""
        CREATE TABLE teams_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            provider TEXT NOT NULL DEFAULT 'espn',
            provider_team_id TEXT NOT NULL,
            primary_league TEXT NOT NULL,
            leagues TEXT NOT NULL DEFAULT '[]',
            sport TEXT NOT NULL,
            team_name TEXT NOT NULL,
            team_abbrev TEXT,
            team_logo_url TEXT,
            team_color TEXT,
            channel_id TEXT NOT NULL UNIQUE,
            channel_logo_url TEXT,
            template_id INTEGER,
            active BOOLEAN DEFAULT 1,
            UNIQUE(provider, provider_team_id, sport),
            FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
        )
    """)

    # Insert consolidated rows
    for row in rows:
        # Convert comma-separated leagues to JSON array
        leagues_list = list(set(row["leagues_concat"].split(","))) if row["leagues_concat"] else []
        leagues_sorted = sorted(leagues_list)
        leagues_json = json.dumps(leagues_sorted)
        # Use first league as primary (will be updated by API if needed)
        primary_league = leagues_sorted[0] if leagues_sorted else ""

        conn.execute(
            """
            INSERT INTO teams_new (
                provider, provider_team_id, primary_league, leagues, sport,
                team_name, team_abbrev, team_logo_url, team_color,
                channel_id, channel_logo_url, template_id, active,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["provider"],
                row["provider_team_id"],
                primary_league,
                leagues_json,
                row["sport"],
                row["team_name"],
                row["team_abbrev"],
                row["team_logo_url"],
                row["team_color"],
                row["channel_id"],
                row["channel_logo_url"],
                row["template_id"],
                row["active"],
                row["created_at"],
                row["updated_at"],
            ),
        )

    # Drop old table and rename new one
    conn.execute("DROP TABLE teams")
    conn.execute("ALTER TABLE teams_new RENAME TO teams")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_channel_id ON teams(channel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_provider ON teams(provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_sport ON teams(sport)")

    # Recreate trigger
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS update_teams_timestamp
        AFTER UPDATE ON teams
        BEGIN
            UPDATE teams SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """)

    logger.info(f"Migrated {len(rows)} teams with leagues arrays")
    return True


def _add_column_if_not_exists(
    conn: sqlite3.Connection, table: str, column: str, column_def: str
) -> None:
    """Add a column to a table if it doesn't exist.

    Args:
        conn: Database connection
        table: Table name
        column: Column name to add
        column_def: Column definition (type and default)
    """
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = {row["name"] for row in cursor.fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")


def reset_db(db_path: Path | str | None = None) -> None:
    """Reset database - drops all tables and reinitializes.

    WARNING: This deletes all data!

    Args:
        db_path: Path to database file. Uses DEFAULT_DB_PATH if not specified.
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH

    if path.exists():
        path.unlink()

    init_db(path)
