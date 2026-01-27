# Database Migrations

This document explains how database migrations work in Teamarr v2 and how to add new migrations.

## Architecture Overview

Teamarr uses a **checkpoint + incremental migration** system:

```
┌─────────────────────────────────────────────────────────────┐
│                    Fresh Install                             │
│                         │                                    │
│                         ▼                                    │
│                   schema.sql                                 │
│              (creates v43 directly)                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               Existing Database (v2-v42)                     │
│                         │                                    │
│                         ▼                                    │
│              checkpoint_v43.py                               │
│         (idempotent, brings any version to v43)              │
│                         │                                    │
│                         ▼                                    │
│              v44, v45, ... migrations                        │
│            (incremental, in connection.py)                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `schema.sql` | Authoritative schema for fresh installs (always current version) |
| `checkpoint_v43.py` | Consolidates v2-v43 migrations into single idempotent operation |
| `connection.py` | Contains `_run_migrations()` which calls checkpoint + incremental migrations |

## Adding a New Migration (v44+)

### Step 1: Update schema.sql

Add your new columns, tables, or indexes to `schema.sql`. This ensures fresh installs get the new schema directly.

```sql
-- Example: Adding a new column to settings
CREATE TABLE settings (
    ...
    my_new_setting TEXT DEFAULT 'default_value',  -- ADD THIS
    schema_version INTEGER DEFAULT 44             -- UPDATE THIS
);
```

**Important**: Also update `schema_version` default to your new version number.

### Step 2: Add Migration to connection.py

Add your migration at the end of `_run_migrations()`, after the checkpoint:

```python
def _run_migrations(conn: sqlite3.Connection) -> None:
    # ... existing code ...

    # Checkpoint handles v2-v43
    if current_version < 43:
        apply_checkpoint_v43(conn, current_version)
        current_version = 43

    # ==========================================================================
    # v44: Your Feature Name
    # ==========================================================================
    if current_version < 44:
        # Add new column (idempotent helper)
        _add_column_if_not_exists(
            conn, "settings", "my_new_setting", "TEXT DEFAULT 'default_value'"
        )

        # Update version
        conn.execute("UPDATE settings SET schema_version = 44 WHERE id = 1")
        logger.info("[MIGRATE] Schema upgraded to version 44 (your feature name)")
        current_version = 44
```

### Step 3: Write Tests

Add tests in `tests/test_migrations.py` or create a specific test file:

```python
def test_v44_migration(temp_db):
    """Test v44 migration adds my_new_setting column."""
    conn, _ = temp_db
    # Create v43 schema
    # Run migration
    # Assert column exists with correct default
```

## Migration Best Practices

### DO: Use Idempotent Operations

```python
# GOOD: Safe to run multiple times
_add_column_if_not_exists(conn, "table", "column", "TYPE DEFAULT value")

# GOOD: INSERT OR IGNORE for seed data
conn.execute("INSERT OR IGNORE INTO sports (code, name) VALUES ('new', 'New Sport')")

# GOOD: UPDATE with WHERE clause that's safe to re-run
conn.execute("UPDATE settings SET new_col = 'value' WHERE new_col IS NULL")
```

### DON'T: Use Destructive Operations Without Guards

```python
# BAD: Will fail if column doesn't exist
conn.execute("ALTER TABLE foo DROP COLUMN bar")

# BETTER: Check first
if "bar" in _get_table_columns(conn, "foo"):
    # SQLite < 3.35 doesn't support DROP COLUMN
    # May need table recreation instead
```

### DO: Check Column/Table Existence Before Data Operations

```python
# GOOD: Defensive data migration
if _table_exists(conn, "my_table"):
    columns = _get_table_columns(conn, "my_table")
    if "target_column" in columns:
        conn.execute("UPDATE my_table SET target_column = 'new' WHERE ...")
```

### DON'T: Add Columns with Non-Constant Defaults

```python
# BAD: SQLite can't add columns with CURRENT_TIMESTAMP default
_add_column_if_not_exists(conn, "t", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

# GOOD: Use NULL or constant default, populate separately
_add_column_if_not_exists(conn, "t", "created_at", "TIMESTAMP")
conn.execute("UPDATE t SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
```

## Helper Functions Available

### `_add_column_if_not_exists(conn, table, column, definition)`
Adds a column only if it doesn't exist. Safe to call multiple times.

### `_table_exists(conn, table) -> bool`
Check if a table exists in the database.

### `_get_table_columns(conn, table) -> set[str]`
Get all column names for a table.

### `_index_exists(conn, index_name) -> bool`
Check if an index exists.

## When to Create a New Checkpoint

Consider creating a new checkpoint (e.g., `checkpoint_v60.py`) when:

1. **Accumulated migrations exceed ~20** since the last checkpoint
2. **Migration code is getting unwieldy** to maintain
3. **Major schema restructure** that would benefit from consolidation

To create a new checkpoint:

1. Copy `checkpoint_v43.py` as `checkpoint_vXX.py`
2. Update all schema definitions to match current `schema.sql`
3. Add any new data transformations
4. Update `connection.py` to use the new checkpoint
5. The old checkpoint can be removed (users below v43 would need to update to an intermediate version first, or you keep both checkpoints)

## Schema Version History

| Version | Description |
|---------|-------------|
| 2 | Initial V2 schema |
| 3-42 | Various additions (consolidated in checkpoint) |
| 43 | Checkpoint baseline |
| 44+ | Future migrations |

## Troubleshooting

### "no such column" errors during migration
The migration is trying to update a column that doesn't exist yet. Add a column existence check before the UPDATE.

### Migration runs but changes aren't visible
Check that `schema_version` is being updated. The version check prevents re-running migrations.

### Fresh install has wrong schema version
Update the `schema_version` default in `schema.sql` to match the latest migration.

### User reports partial migration
The checkpoint handles this - it's idempotent and will fill in any missing pieces. If the issue is with a v44+ migration, ensure the migration code is idempotent.
