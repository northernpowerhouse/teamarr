"""Broadcast variables: TV networks, national broadcast status.

These variables provide broadcast information for games.
"""

from teamarr.templates.context import GameContext, TemplateContext
from teamarr.templates.variables.registry import (
    Category,
    SuffixRules,
    register_variable,
)

# Subscription services - sort these last (still visible, just deprioritized)
SUBSCRIPTION_NETWORKS = {
    "NBA League Pass",
    "NHL.TV",
    "ESPN+",
    "Peacock",
    "MLB.TV",
    "MLS Season Pass",
}

# National broadcast networks (priority order)
NATIONAL_NETWORKS = {
    "ABC",
    "CBS",
    "NBC",
    "FOX",
    "ESPN",
    "ESPN2",
    "TNT",
    "TBS",
    "NFL Network",
    "NBA TV",
    "NHL Network",
    "MLB Network",
    "FS1",
    "FS2",
    "USA Network",
}


def _get_broadcasts(game_ctx: GameContext | None) -> list[str]:
    """Get broadcast networks from event."""
    if not game_ctx or not game_ctx.event:
        return []
    return game_ctx.event.broadcasts or []


def _sort_broadcasts(broadcasts: list[str]) -> list[str]:
    """Sort broadcasts: national first, regional middle, subscription last."""
    national = [b for b in broadcasts if b in NATIONAL_NETWORKS]
    subscription = [b for b in broadcasts if b in SUBSCRIPTION_NETWORKS]
    other = [b for b in broadcasts if b not in NATIONAL_NETWORKS and b not in SUBSCRIPTION_NETWORKS]
    return national + other + subscription


@register_variable(
    name="broadcast_simple",
    category=Category.BROADCAST,
    suffix_rules=SuffixRules.ALL,
    description="Comma-separated broadcast networks (e.g., 'ESPN, ABC')",
)
def extract_broadcast_simple(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    broadcasts = _get_broadcasts(game_ctx)
    sorted_broadcasts = _sort_broadcasts(broadcasts)
    return ", ".join(sorted_broadcasts)


@register_variable(
    name="broadcast_network",
    category=Category.BROADCAST,
    suffix_rules=SuffixRules.ALL,
    description="Primary broadcast network (first in list)",
)
def extract_broadcast_network(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    broadcasts = _get_broadcasts(game_ctx)
    sorted_broadcasts = _sort_broadcasts(broadcasts)
    return sorted_broadcasts[0] if sorted_broadcasts else ""


@register_variable(
    name="broadcast_national_network",
    category=Category.BROADCAST,
    suffix_rules=SuffixRules.ALL,
    description="National broadcast networks only",
)
def extract_broadcast_national_network(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    broadcasts = _get_broadcasts(game_ctx)
    national = [b for b in broadcasts if b in NATIONAL_NETWORKS]
    return ", ".join(national)


@register_variable(
    name="is_national_broadcast",
    category=Category.BROADCAST,
    suffix_rules=SuffixRules.ALL,
    description="'true' if game is on national TV",
)
def extract_is_national_broadcast(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    broadcasts = _get_broadcasts(game_ctx)
    has_national = any(b in NATIONAL_NETWORKS for b in broadcasts)
    return "true" if has_national else "false"
