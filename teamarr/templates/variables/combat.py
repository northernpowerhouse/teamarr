"""Combat sports template variables (UFC, Boxing, MMA).

Variables for UFC card segments, fighter names, and matchup formatting.
"""

from teamarr.templates.context import GameContext, TemplateContext
from teamarr.templates.variables.registry import (
    Category,
    SuffixRules,
    register_variable,
)


@register_variable(
    name="fighter1",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="First fighter name (headline bout home_team)",
)
def extract_fighter1(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract first fighter name from UFC event.

    For UFC events, home_team and away_team represent fighters in the headline bout.
    """
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    if event.home_team and event.home_team.name:
        return event.home_team.name

    return ""


@register_variable(
    name="fighter2",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Second fighter name (headline bout away_team)",
)
def extract_fighter2(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract second fighter name from UFC event."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    if event.away_team and event.away_team.name:
        return event.away_team.name

    return ""


@register_variable(
    name="matchup",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Full matchup (Fighter1 vs Fighter2)",
)
def extract_matchup(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract full matchup string from UFC event."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    fighter1 = event.home_team.name if event.home_team else ""
    fighter2 = event.away_team.name if event.away_team else ""

    if fighter1 and fighter2:
        return f"{fighter1} vs {fighter2}"
    elif fighter1:
        return fighter1
    elif fighter2:
        return fighter2

    return ""


@register_variable(
    name="event_number",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="UFC event number (e.g., '325' from 'UFC 325')",
)
def extract_event_number(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract event number from UFC event name."""
    import re

    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    # Try to extract number from event name
    # "UFC 325: Volkanovski vs Lopes" -> "325"
    match = re.search(r"UFC\s*(\d+)", event.name, re.IGNORECASE)
    if match:
        return match.group(1)

    # Try short_name
    match = re.search(r"UFC\s*(\d+)", event.short_name, re.IGNORECASE)
    if match:
        return match.group(1)

    return ""


@register_variable(
    name="event_title",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Full event title (e.g., 'UFC 325: Volkanovski vs Lopes')",
)
def extract_event_title(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract full event title from UFC event."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    return event.name


# =============================================================================
# Card Segment Variables
# =============================================================================

# Display names for template output
SEGMENT_DISPLAY_NAMES: dict[str, str] = {
    "early_prelims": "Early Prelims",
    "prelims": "Prelims",
    "main_card": "Main Card",
}


@register_variable(
    name="card_segment",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.NONE,  # Segment is specific to current channel, no .next/.last
    description="Card segment code (early_prelims, prelims, main_card)",
)
def extract_card_segment(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract card segment for this UFC channel.

    Returns the segment code assigned to this specific stream/channel.
    Used for conditional logic and routing in templates.
    """
    if not game_ctx:
        return ""

    return game_ctx.card_segment or ""


@register_variable(
    name="card_segment_display",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.NONE,  # Segment is specific to current channel
    description="Card segment display name (Early Prelims, Prelims, Main Card)",
)
def extract_card_segment_display(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract human-readable card segment name.

    Converts segment code to display format:
    - early_prelims -> "Early Prelims"
    - prelims -> "Prelims"
    - main_card -> "Main Card"
    """
    if not game_ctx or not game_ctx.card_segment:
        return ""

    segment = game_ctx.card_segment
    return SEGMENT_DISPLAY_NAMES.get(segment, segment.replace("_", " ").title())


# =============================================================================
# Segment Time Variables
# =============================================================================


@register_variable(
    name="main_card_time",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Main card start time (e.g., '10:00 PM EST')",
)
def extract_main_card_time(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract main card start time from ESPN segment data."""
    from teamarr.utilities.tz import format_time

    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.segment_times:
        return ""

    main_card_dt = event.segment_times.get("main_card")
    if not main_card_dt:
        return ""

    return format_time(main_card_dt)


@register_variable(
    name="prelims_time",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Prelims start time (e.g., '8:00 PM EST')",
)
def extract_prelims_time(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract prelims start time from ESPN segment data."""
    from teamarr.utilities.tz import format_time

    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.segment_times:
        return ""

    prelims_dt = event.segment_times.get("prelims")
    if not prelims_dt:
        return ""

    return format_time(prelims_dt)


@register_variable(
    name="early_prelims_time",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Early prelims start time (e.g., '6:00 PM EST')",
)
def extract_early_prelims_time(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Extract early prelims start time from ESPN segment data."""
    from teamarr.utilities.tz import format_time

    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.segment_times:
        return ""

    early_dt = event.segment_times.get("early_prelims")
    if not early_dt:
        return ""

    return format_time(early_dt)


# =============================================================================
# Bout Card Variables - All fighter pairings on the card
# =============================================================================


@register_variable(
    name="bout_count",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Total number of bouts on the card",
)
def extract_bout_count(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Return total number of bouts on the UFC card."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma":
        return ""

    return str(len(event.bouts)) if event.bouts else ""


@register_variable(
    name="fight_card",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="All bouts formatted as 'Fighter1 vs Fighter2' (newline-separated)",
)
def extract_fight_card(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Return all bouts on the card, formatted and newline-separated.

    Bouts are ordered from opener to main event.
    """
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.bouts:
        return ""

    return "\n".join(f"{b.fighter1} vs {b.fighter2}" for b in event.bouts)


@register_variable(
    name="main_card_bouts",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Main card bouts only (newline-separated)",
)
def extract_main_card_bouts(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Return main card bouts only, formatted and newline-separated."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.bouts:
        return ""

    main_bouts = [b for b in event.bouts if b.segment == "main_card"]
    return "\n".join(f"{b.fighter1} vs {b.fighter2}" for b in main_bouts)


@register_variable(
    name="prelims_bouts",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Prelims bouts only (newline-separated)",
)
def extract_prelims_bouts(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Return prelims bouts only, formatted and newline-separated."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.bouts:
        return ""

    prelim_bouts = [b for b in event.bouts if b.segment == "prelims"]
    return "\n".join(f"{b.fighter1} vs {b.fighter2}" for b in prelim_bouts)


@register_variable(
    name="early_prelims_bouts",
    category=Category.COMBAT,
    suffix_rules=SuffixRules.ALL,
    description="Early prelims bouts only (newline-separated)",
)
def extract_early_prelims_bouts(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    """Return early prelims bouts only, formatted and newline-separated."""
    if not game_ctx or not game_ctx.event:
        return ""

    event = game_ctx.event
    if event.sport != "mma" or not event.bouts:
        return ""

    early_bouts = [b for b in event.bouts if b.segment == "early_prelims"]
    return "\n".join(f"{b.fighter1} vs {b.fighter2}" for b in early_bouts)
