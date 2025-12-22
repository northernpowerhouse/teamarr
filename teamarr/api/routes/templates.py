"""Templates API endpoints."""

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from teamarr.api.models import (
    TemplateCreate,
    TemplateFullResponse,
    TemplateResponse,
    TemplateUpdate,
)
from teamarr.database import get_db

router = APIRouter()


def _parse_json_fields(row: dict) -> dict:
    """Parse JSON string fields into Python objects."""
    result = dict(row)
    json_fields = [
        "xmltv_flags",
        "xmltv_categories",
        "pregame_periods",
        "pregame_fallback",
        "postgame_periods",
        "postgame_fallback",
        "postgame_conditional",
        "idle_content",
        "idle_conditional",
        "idle_offseason",
        "conditional_descriptions",
    ]
    for field in json_fields:
        if field in result and result[field]:
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


@router.get("/templates", response_model=list[TemplateResponse])
def list_templates():
    """List all templates with usage counts."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT t.*,
                   COALESCE((SELECT COUNT(*) FROM teams WHERE template_id = t.id), 0) as team_count,
                   COALESCE((SELECT COUNT(*) FROM event_epg_groups WHERE template_id = t.id), 0) as group_count
            FROM templates t
            ORDER BY t.name
            """
        )
        return [dict(row) for row in cursor.fetchall()]


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(template: TemplateCreate):
    """Create a new template."""
    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO templates (
                    name, template_type, sport, league,
                    title_format, subtitle_template, description_template, program_art_url,
                    game_duration_mode, game_duration_override,
                    xmltv_flags, xmltv_categories, categories_apply_to,
                    pregame_enabled, pregame_periods, pregame_fallback,
                    postgame_enabled, postgame_periods, postgame_fallback, postgame_conditional,
                    idle_enabled, idle_content, idle_conditional, idle_offseason,
                    conditional_descriptions,
                    event_channel_name, event_channel_logo_url
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    template.name,
                    template.template_type,
                    template.sport,
                    template.league,
                    template.title_format,
                    template.subtitle_template,
                    template.description_template,
                    template.program_art_url,
                    template.game_duration_mode,
                    template.game_duration_override,
                    json.dumps(template.xmltv_flags) if template.xmltv_flags else None,
                    json.dumps(template.xmltv_categories) if template.xmltv_categories else None,
                    template.categories_apply_to,
                    template.pregame_enabled,
                    json.dumps([p.model_dump() for p in template.pregame_periods])
                    if template.pregame_periods
                    else None,
                    json.dumps(template.pregame_fallback.model_dump())
                    if template.pregame_fallback
                    else None,
                    template.postgame_enabled,
                    json.dumps([p.model_dump() for p in template.postgame_periods])
                    if template.postgame_periods
                    else None,
                    json.dumps(template.postgame_fallback.model_dump())
                    if template.postgame_fallback
                    else None,
                    json.dumps(template.postgame_conditional.model_dump())
                    if template.postgame_conditional
                    else None,
                    template.idle_enabled,
                    json.dumps(template.idle_content.model_dump())
                    if template.idle_content
                    else None,
                    json.dumps(template.idle_conditional.model_dump())
                    if template.idle_conditional
                    else None,
                    json.dumps(template.idle_offseason.model_dump())
                    if template.idle_offseason
                    else None,
                    json.dumps([c.model_dump() for c in template.conditional_descriptions])
                    if template.conditional_descriptions
                    else None,
                    template.event_channel_name,
                    template.event_channel_logo_url,
                ),
            )
            template_id = cursor.lastrowid
            cursor = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            return dict(cursor.fetchone())
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Template with this name already exists",
                ) from None
            raise


@router.get("/templates/{template_id}", response_model=TemplateFullResponse)
def get_template(template_id: int):
    """Get a template by ID with all JSON fields parsed."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        return _parse_json_fields(dict(row))


def _serialize_for_db(key: str, value):
    """Serialize value for database storage."""
    json_fields = {
        "xmltv_flags",
        "xmltv_categories",
        "pregame_periods",
        "pregame_fallback",
        "postgame_periods",
        "postgame_fallback",
        "postgame_conditional",
        "idle_content",
        "idle_conditional",
        "idle_offseason",
        "conditional_descriptions",
    }
    if key in json_fields and value is not None:
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump())
        elif isinstance(value, list):
            return json.dumps([v.model_dump() if hasattr(v, "model_dump") else v for v in value])
        elif isinstance(value, dict):
            return json.dumps(value)
    return value


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, template: TemplateUpdate):
    """Update a template."""
    updates = {k: v for k, v in template.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    # Serialize JSON fields
    serialized = {k: _serialize_for_db(k, v) for k, v in updates.items()}

    set_clause = ", ".join(f"{k} = ?" for k in serialized.keys())
    values = list(serialized.values()) + [template_id]

    with get_db() as conn:
        cursor = conn.execute(f"UPDATE templates SET {set_clause} WHERE id = ?", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        cursor = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        return dict(cursor.fetchone())


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int):
    """Delete a template."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


# V1 Migration


class V1MigrateRequest(BaseModel):
    """Request to migrate templates from V1 database."""

    v1_db_path: str


class V1MigrateResponse(BaseModel):
    """Response from V1 migration."""

    success: bool
    migrated_count: int
    templates: list[str]
    message: str


def _parse_v1_json(value, default=None):
    """Parse JSON string from V1, returning default on failure."""
    if value is None:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def _convert_v1_to_v2(v1_row: dict) -> dict:
    """Convert V1 template row to V2 format."""
    # Parse V1 JSON fields
    v1_flags = _parse_v1_json(v1_row.get("flags"), {"new": True, "live": False, "date": False})
    v1_categories = _parse_v1_json(v1_row.get("categories"), ["Sports"])
    v1_description_options = _parse_v1_json(v1_row.get("description_options"), [])

    # Build V2 pregame_fallback from V1 individual fields
    pregame_fallback = {
        "title": v1_row.get("pregame_title") or "Pregame Coverage",
        "subtitle": v1_row.get("pregame_subtitle"),
        "description": v1_row.get("pregame_description"),
        "art_url": v1_row.get("pregame_art_url"),
    }

    # Build V2 postgame_fallback from V1 individual fields
    postgame_fallback = {
        "title": v1_row.get("postgame_title") or "Postgame Recap",
        "subtitle": v1_row.get("postgame_subtitle"),
        "description": v1_row.get("postgame_description"),
        "art_url": v1_row.get("postgame_art_url"),
    }

    # Build V2 postgame_conditional from V1 fields
    postgame_conditional = {
        "enabled": bool(v1_row.get("postgame_conditional_enabled")),
        "description_final": v1_row.get("postgame_description_final"),
        "description_not_final": v1_row.get("postgame_description_not_final"),
    }

    # Build V2 idle_content from V1 individual fields
    idle_content = {
        "title": v1_row.get("idle_title") or "{team_name} Programming",
        "subtitle": v1_row.get("idle_subtitle"),
        "description": v1_row.get("idle_description"),
        "art_url": v1_row.get("idle_art_url"),
    }

    # Build V2 idle_conditional from V1 fields
    idle_conditional = {
        "enabled": bool(v1_row.get("idle_conditional_enabled")),
        "description_final": v1_row.get("idle_description_final"),
        "description_not_final": v1_row.get("idle_description_not_final"),
    }

    # Build V2 idle_offseason from V1 fields
    idle_offseason = {
        "title_enabled": bool(v1_row.get("idle_title_offseason_enabled")),
        "title": v1_row.get("idle_title_offseason"),
        "subtitle_enabled": bool(v1_row.get("idle_subtitle_offseason_enabled")),
        "subtitle": v1_row.get("idle_subtitle_offseason"),
        "description_enabled": bool(v1_row.get("idle_offseason_enabled")),
        "description": v1_row.get("idle_description_offseason"),
    }

    # Map V1 to V2 fields
    return {
        "name": v1_row.get("name"),
        "template_type": v1_row.get("template_type") or "team",
        "sport": v1_row.get("sport"),
        "league": v1_row.get("league"),
        "title_format": v1_row.get("title_format"),
        "subtitle_template": v1_row.get("subtitle_template"),
        "description_template": None,  # V2 uses conditional_descriptions instead
        "program_art_url": v1_row.get("program_art_url"),
        "game_duration_mode": v1_row.get("game_duration_mode") or "sport",
        "game_duration_override": v1_row.get("game_duration_override"),
        "xmltv_flags": json.dumps(v1_flags),
        "xmltv_categories": json.dumps(v1_categories),
        "categories_apply_to": v1_row.get("categories_apply_to") or "all",
        "pregame_enabled": bool(v1_row.get("pregame_enabled")),
        "pregame_periods": json.dumps([]),  # V2 uses periods array, V1 didn't
        "pregame_fallback": json.dumps(pregame_fallback),
        "postgame_enabled": bool(v1_row.get("postgame_enabled")),
        "postgame_periods": json.dumps([]),  # V2 uses periods array, V1 didn't
        "postgame_fallback": json.dumps(postgame_fallback),
        "postgame_conditional": json.dumps(postgame_conditional),
        "idle_enabled": bool(v1_row.get("idle_enabled")),
        "idle_content": json.dumps(idle_content),
        "idle_conditional": json.dumps(idle_conditional),
        "idle_offseason": json.dumps(idle_offseason),
        "conditional_descriptions": json.dumps(v1_description_options),
        "event_channel_name": v1_row.get("channel_name"),
        "event_channel_logo_url": v1_row.get("channel_logo_url"),
    }


@router.post("/templates/migrate-v1", response_model=V1MigrateResponse)
def migrate_v1_templates(request: V1MigrateRequest):
    """Migrate templates from V1 database.

    Converts V1 template format to V2's restructured format.
    Skips migration if V2 already has templates with the same name.
    """
    v1_path = Path(request.v1_db_path)

    if not v1_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"V1 database not found at {v1_path}",
        )

    # Read V1 templates
    try:
        v1_conn = sqlite3.connect(v1_path)
        v1_conn.row_factory = sqlite3.Row
        cursor = v1_conn.execute("SELECT * FROM templates")
        v1_templates = [dict(row) for row in cursor.fetchall()]
        v1_conn.close()
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading V1 database: {e}",
        ) from None

    if not v1_templates:
        return V1MigrateResponse(
            success=True,
            migrated_count=0,
            templates=[],
            message="No templates found in V1 database",
        )

    # Get existing V2 template names to avoid duplicates
    with get_db() as conn:
        cursor = conn.execute("SELECT name FROM templates")
        existing_names = {row["name"] for row in cursor.fetchall()}

    # Convert and insert templates
    migrated = []
    skipped = []

    with get_db() as conn:
        for v1_row in v1_templates:
            v2_template = _convert_v1_to_v2(v1_row)
            name = v2_template["name"]

            if name in existing_names:
                skipped.append(name)
                continue

            columns = list(v2_template.keys())
            placeholders = ", ".join("?" * len(columns))
            column_str = ", ".join(columns)
            values = [v2_template[col] for col in columns]

            conn.execute(
                f"INSERT INTO templates ({column_str}) VALUES ({placeholders})",
                values,
            )
            migrated.append(name)

    message_parts = []
    if migrated:
        message_parts.append(f"Migrated {len(migrated)} template(s)")
    if skipped:
        message_parts.append(f"Skipped {len(skipped)} existing: {', '.join(skipped)}")

    return V1MigrateResponse(
        success=True,
        migrated_count=len(migrated),
        templates=migrated,
        message=". ".join(message_parts) if message_parts else "No templates to migrate",
    )
