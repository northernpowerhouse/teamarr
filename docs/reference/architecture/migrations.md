---
title: Database Migrations
parent: Architecture
grand_parent: Technical Reference
nav_order: 6
---

# Database Migrations

Teamarr uses a **checkpoint + incremental migration** system to handle database schema changes safely across versions.

## Architecture

```
Fresh Install          Existing Database (v2-v42)      Existing Database (v43+)
     │                          │                              │
     ▼                          ▼                              ▼
 schema.sql              checkpoint_v43.py              Skip checkpoint
(creates v43)         (idempotent → v43)                      │
     │                          │                              │
     └──────────────────────────┴──────────────────────────────┘
                                │
                                ▼
                    v44, v45, ... incremental
                    migrations (connection.py)
```

### Key Principles

1. **Idempotent**: Migrations can be run multiple times safely
2. **Defensive**: Check column/table existence before operations
3. **Checkpoint-based**: Old migrations consolidated, new ones are incremental

## Key Files

| File | Purpose |
|------|---------|
| `teamarr/database/schema.sql` | Authoritative schema for fresh installs |
| `teamarr/database/checkpoint_v43.py` | Consolidates v2-v43 into single operation |
| `teamarr/database/connection.py` | `_run_migrations()` orchestrates everything |

## How It Works

### Fresh Install
1. `schema.sql` creates database directly at current version (v43+)
2. No migrations run

### Existing Database (v2-v42)
1. `apply_checkpoint_v43()` runs
2. Checkpoint is **idempotent** - ensures v43 state regardless of starting point
3. Handles partial migrations gracefully
4. Any v44+ migrations run afterward

### Existing Database (v43+)
1. Checkpoint is skipped (version check)
2. Only v44+ migrations run if needed

## Adding a New Migration

### 1. Update schema.sql

Add new columns/tables and update the default schema version:

```sql
CREATE TABLE settings (
    ...
    my_new_setting TEXT DEFAULT 'value',
    schema_version INTEGER DEFAULT 44  -- Bump this
);
```

### 2. Add Migration to connection.py

Add after the checkpoint call in `_run_migrations()`:

```python
# v44: My Feature
if current_version < 44:
    _add_column_if_not_exists(
        conn, "settings", "my_new_setting", "TEXT DEFAULT 'value'"
    )
    conn.execute("UPDATE settings SET schema_version = 44 WHERE id = 1")
    logger.info("[MIGRATE] Schema upgraded to version 44")
    current_version = 44
```

### 3. Write Tests

```python
def test_v44_migration(temp_db):
    # Setup v43 database
    # Run _run_migrations
    # Assert new column exists
```

## Best Practices

### Use Idempotent Operations

```python
# Safe to run multiple times
_add_column_if_not_exists(conn, "table", "col", "TYPE DEFAULT val")

# Safe INSERT
conn.execute("INSERT OR IGNORE INTO sports (code, name) VALUES ('x', 'X')")

# Safe UPDATE
conn.execute("UPDATE t SET col = 'new' WHERE col IS NULL")
```

### Check Before Operating

```python
if _table_exists(conn, "my_table"):
    columns = _get_table_columns(conn, "my_table")
    if "target_col" in columns:
        conn.execute("UPDATE my_table SET target_col = ...")
```

### Avoid Non-Constant Defaults

```python
# BAD: SQLite can't add CURRENT_TIMESTAMP default
_add_column_if_not_exists(conn, "t", "created", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

# GOOD: Add with NULL, populate separately
_add_column_if_not_exists(conn, "t", "created", "TIMESTAMP")
conn.execute("UPDATE t SET created = CURRENT_TIMESTAMP WHERE created IS NULL")
```

## Available Helper Functions

| Function | Purpose |
|----------|---------|
| `_add_column_if_not_exists(conn, table, col, def)` | Add column if missing |
| `_table_exists(conn, table)` | Check if table exists |
| `_get_table_columns(conn, table)` | Get column names as set |
| `_index_exists(conn, name)` | Check if index exists |

## When to Create a New Checkpoint

Consider a new checkpoint when:
- 15-20+ migrations accumulated since last checkpoint
- Major schema restructure planned
- Migration code becoming unwieldy

To create:
1. Copy `checkpoint_v43.py` to `checkpoint_vXX.py`
2. Update all schema definitions to match current `schema.sql`
3. Update `connection.py` to use new checkpoint
4. Old checkpoint can be removed (or kept for users on very old versions)

## Version History

| Version | Type | Description |
|---------|------|-------------|
| 2 | Base | Initial V2 schema |
| 3-42 | Checkpoint | Consolidated into checkpoint_v43 |
| 43 | Checkpoint | Checkpoint baseline |
| 44+ | Incremental | Individual migrations |

## Troubleshooting

### "no such column" during migration
Add column existence check before UPDATE operations.

### Migration runs but nothing changes
Verify `schema_version` is being updated in the migration.

### Fresh install has wrong version
Update `schema_version` default in `schema.sql`.

### User reports partial state
The checkpoint handles this - it fills in missing pieces idempotently.
