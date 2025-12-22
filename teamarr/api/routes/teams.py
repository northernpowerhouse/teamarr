"""Teams API endpoints."""

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from teamarr.api.models import TeamCreate, TeamResponse, TeamUpdate
from teamarr.database import get_db

router = APIRouter()


def generate_channel_id(team_name: str, primary_league: str) -> str:
    """Generate channel ID from team name and league."""
    from teamarr.database.leagues import get_league_id

    name = "".join(
        word.capitalize()
        for word in "".join(c if c.isalnum() or c.isspace() else "" for c in team_name).split()
    )

    with get_db() as conn:
        league_id = get_league_id(conn, primary_league)

    return f"{name}.{league_id}"


def _parse_leagues(leagues_str: str | None) -> list[str]:
    """Parse leagues JSON string to list."""
    if not leagues_str:
        return []
    try:
        return json.loads(leagues_str)
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_response(row) -> dict:
    """Convert database row to response dict with parsed leagues."""
    data = dict(row)
    data["leagues"] = _parse_leagues(data.get("leagues"))
    return data


class BulkImportTeam(BaseModel):
    """Team data from cache for bulk import."""

    team_name: str
    team_abbrev: str | None = None
    provider: str
    provider_team_id: str
    league: str  # League this team was found in
    sport: str
    logo_url: str | None = None


class BulkImportRequest(BaseModel):
    """Bulk import request body."""

    teams: list[BulkImportTeam]


class BulkImportResponse(BaseModel):
    """Bulk import result."""

    imported: int
    updated: int  # Teams that had new leagues added
    skipped: int


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(active_only: bool = False):
    """List all teams."""
    with get_db() as conn:
        if active_only:
            cursor = conn.execute("SELECT * FROM teams WHERE active = 1 ORDER BY team_name")
        else:
            cursor = conn.execute("SELECT * FROM teams ORDER BY team_name")
        return [_row_to_response(row) for row in cursor.fetchall()]


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(team: TeamCreate):
    """Create a new team."""
    # Ensure primary_league is in leagues list
    leagues = list(set(team.leagues + [team.primary_league]))
    leagues_json = json.dumps(sorted(leagues))

    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO teams (
                    provider, provider_team_id, primary_league, leagues, sport,
                    team_name, team_abbrev, team_logo_url, team_color,
                    channel_id, channel_logo_url, template_id, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team.provider,
                    team.provider_team_id,
                    team.primary_league,
                    leagues_json,
                    team.sport,
                    team.team_name,
                    team.team_abbrev,
                    team.team_logo_url,
                    team.team_color,
                    team.channel_id,
                    team.channel_logo_url,
                    team.template_id,
                    team.active,
                ),
            )
            team_id = cursor.lastrowid
            cursor = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
            return _row_to_response(cursor.fetchone())
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Team with this channel_id or provider/team_id/sport already exists",
                ) from None
            raise


@router.get("/teams/{team_id}", response_model=TeamResponse)
def get_team(team_id: int):
    """Get a team by ID."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        return _row_to_response(row)


@router.put("/teams/{team_id}", response_model=TeamResponse)
@router.patch("/teams/{team_id}", response_model=TeamResponse)
def update_team(team_id: int, team: TeamUpdate):
    """Update a team (full or partial)."""
    updates = {k: v for k, v in team.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    # Convert leagues list to JSON if present
    if "leagues" in updates:
        updates["leagues"] = json.dumps(updates["leagues"])

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [team_id]

    with get_db() as conn:
        cursor = conn.execute(f"UPDATE teams SET {set_clause} WHERE id = ?", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        cursor = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
        return _row_to_response(cursor.fetchone())


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int):
    """Delete a team."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")


@router.post("/teams/bulk-import", response_model=BulkImportResponse)
def bulk_import_teams(request: BulkImportRequest):
    """Bulk import teams from cache.

    Consolidates by (provider, provider_team_id, sport):
    - New teams are created with their league in the leagues array
    - Existing teams have new leagues added to their leagues array
    - Skips when league already exists for the team
    """
    imported = 0
    updated = 0
    skipped = 0

    with get_db() as conn:
        # Get existing teams indexed by (provider, provider_team_id, sport)
        cursor = conn.execute("SELECT id, provider, provider_team_id, sport, leagues FROM teams")
        existing: dict[tuple[str, str, str], tuple[int, list[str]]] = {}
        for row in cursor.fetchall():
            key = (row["provider"], row["provider_team_id"], row["sport"])
            leagues = _parse_leagues(row["leagues"])
            existing[key] = (row["id"], leagues)

        for team in request.teams:
            key = (team.provider, team.provider_team_id, team.sport)

            if key in existing:
                # Team exists - check if this league needs to be added
                team_id, current_leagues = existing[key]
                if team.league in current_leagues:
                    skipped += 1
                    continue

                # Add the new league to the existing team
                new_leagues = sorted(set(current_leagues + [team.league]))
                conn.execute(
                    "UPDATE teams SET leagues = ? WHERE id = ?",
                    (json.dumps(new_leagues), team_id),
                )
                existing[key] = (team_id, new_leagues)
                updated += 1
            else:
                # New team - create with this league as primary
                channel_id = generate_channel_id(team.team_name, team.league)
                leagues_json = json.dumps([team.league])

                cursor = conn.execute(
                    """
                    INSERT INTO teams (
                        provider, provider_team_id, primary_league, leagues, sport,
                        team_name, team_abbrev, team_logo_url,
                        channel_id, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        team.provider,
                        team.provider_team_id,
                        team.league,  # First league becomes primary
                        leagues_json,
                        team.sport,
                        team.team_name,
                        team.team_abbrev,
                        team.logo_url,
                        channel_id,
                    ),
                )
                team_id = cursor.lastrowid
                existing[key] = (team_id, [team.league])
                imported += 1

    return BulkImportResponse(imported=imported, updated=updated, skipped=skipped)
