"""Core types and interfaces for Teamarr.

All data structures are dataclasses with attribute access.
Providers implement SportsProvider interface.
"""

from core.interfaces import SportsProvider
from core.types import (
    EnrichedEvent,
    Event,
    EventStatus,
    GameContext,
    HeadToHead,
    Odds,
    PlayerLeaders,
    ProcessedProgramme,
    Programme,
    Streaks,
    Team,
    TeamConfig,
    TeamStats,
    TemplateContext,
    Venue,
)

__all__ = [
    # Types
    "EnrichedEvent",
    "Event",
    "EventStatus",
    "GameContext",
    "HeadToHead",
    "Odds",
    "PlayerLeaders",
    "ProcessedProgramme",
    "Programme",
    "Streaks",
    "Team",
    "TeamConfig",
    "TeamStats",
    "TemplateContext",
    "Venue",
    # Interfaces
    "SportsProvider",
]
