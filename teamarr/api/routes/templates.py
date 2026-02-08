"""Templates API endpoints."""

import json
import logging

from fastapi import APIRouter, HTTPException, status

from teamarr.api.models import (
    TemplateCreate,
    TemplateFullResponse,
    TemplateResponse,
    TemplateUpdate,
)
from teamarr.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# JSON fields that need serialization from Pydantic models to strings
_JSON_FIELDS = {
    "xmltv_flags",
    "xmltv_video",
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


def _serialize_for_db(key: str, value):
    """Serialize a Pydantic model field value for database storage."""
    if key in _JSON_FIELDS and value is not None:
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump())
        elif isinstance(value, list):
            return json.dumps([v.model_dump() if hasattr(v, "model_dump") else v for v in value])
        elif isinstance(value, dict):
            return json.dumps(value)
    return value


def _parse_json_fields(row: dict) -> dict:
    """Parse JSON string fields into Python objects for API response."""
    result = dict(row)
    for field in _JSON_FIELDS:
        if field in result and result[field]:
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


@router.get("/templates", response_model=list[TemplateResponse])
def list_templates():
    """List all templates with usage counts."""
    from teamarr.database.templates import list_templates_with_counts

    with get_db() as conn:
        return list_templates_with_counts(conn)


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(template: TemplateCreate):
    """Create a new template."""
    # Serialize Pydantic model fields for database storage
    data = {k: _serialize_for_db(k, v) for k, v in template.model_dump().items()}

    with get_db() as conn:
        try:
            # Build INSERT dynamically from all non-None fields
            columns = [k for k, v in data.items() if v is not None or k == "name"]
            values = [data[k] for k in columns]
            placeholders = ", ".join("?" * len(columns))
            col_str = ", ".join(columns)

            cursor = conn.execute(
                f"INSERT INTO templates ({col_str}) VALUES ({placeholders})",
                values,
            )
            template_id = cursor.lastrowid
            logger.info("[CREATED] Template id=%d name=%s", template_id, template.name)
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


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, template: TemplateUpdate):
    """Update a template."""
    updates = {k: v for k, v in template.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    serialized = {k: _serialize_for_db(k, v) for k, v in updates.items()}
    set_clause = ", ".join(f"{k} = ?" for k in serialized.keys())
    values = list(serialized.values()) + [template_id]

    with get_db() as conn:
        cursor = conn.execute(f"UPDATE templates SET {set_clause} WHERE id = ?", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        logger.info("[UPDATED] Template id=%d fields=%s", template_id, list(updates.keys()))
        cursor = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        return dict(cursor.fetchone())


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int):
    """Delete a template."""
    from teamarr.database.templates import delete_template as db_delete

    with get_db() as conn:
        if not db_delete(conn, template_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
