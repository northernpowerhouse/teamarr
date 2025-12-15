"""Variable registry and registration decorator.

This module provides the central registry for all template variables.
Variables are registered using the @register_variable decorator, which
captures metadata alongside the extraction function.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core import GameContext, TemplateContext

# Type alias for extractor functions
Extractor = Callable[["TemplateContext", "GameContext | None"], str]


class Category(Enum):
    """Variable categories for organization and documentation."""

    IDENTITY = auto()  # team_name, opponent, league
    DATETIME = auto()  # game_date, game_time
    VENUE = auto()  # venue, venue_city
    HOME_AWAY = auto()  # is_home, vs_at
    RECORDS = auto()  # team_record, opponent_record
    STREAKS = auto()  # streak, home_streak
    H2H = auto()  # season_series, rematch_*
    SCORES = auto()  # team_score, final_score
    OUTCOME = auto()  # result, result_text
    STANDINGS = auto()  # playoff_seed, games_back
    STATISTICS = auto()  # team_ppg, opponent_ppg
    PLAYOFFS = auto()  # is_playoff, season_type
    ODDS = auto()  # odds_spread, odds_over_under
    BROADCAST = auto()  # broadcast_simple
    RANKINGS = auto()  # team_rank, is_ranked
    CONFERENCE = auto()  # college_conference, pro_division
    SOCCER = auto()  # soccer_match_league
    PLAYER_LEADERS = auto()  # scoring_leader_*


# Category display metadata for UI
CATEGORY_DISPLAY = {
    Category.IDENTITY: {"label": "Team Identity", "icon": "🏷️"},
    Category.DATETIME: {"label": "Date & Time", "icon": "📅"},
    Category.VENUE: {"label": "Venue", "icon": "🏟️"},
    Category.HOME_AWAY: {"label": "Home/Away", "icon": "🏠"},
    Category.RECORDS: {"label": "Records", "icon": "📊"},
    Category.STREAKS: {"label": "Streaks", "icon": "🔥"},
    Category.H2H: {"label": "Head-to-Head", "icon": "⚔️"},
    Category.SCORES: {"label": "Scores", "icon": "🎯"},
    Category.OUTCOME: {"label": "Outcome", "icon": "🏆"},
    Category.STANDINGS: {"label": "Standings", "icon": "📈"},
    Category.STATISTICS: {"label": "Statistics", "icon": "📉"},
    Category.PLAYOFFS: {"label": "Season Type", "icon": "🏅"},
    Category.ODDS: {"label": "Betting Odds", "icon": "💰"},
    Category.BROADCAST: {"label": "Broadcast", "icon": "📺"},
    Category.RANKINGS: {"label": "Rankings", "icon": "🎖️"},
    Category.CONFERENCE: {"label": "Conference/Division", "icon": "🏛️"},
    Category.SOCCER: {"label": "Soccer", "icon": "⚽"},
    Category.PLAYER_LEADERS: {"label": "Player Leaders", "icon": "👤"},
}


class SuffixRules(Enum):
    """Rules for which suffixes a variable supports.

    Variables are generated for base (current game), .next (next game),
    and .last (last game) contexts. Different variables have different
    rules about which suffixes make sense.
    """

    ALL = auto()  # base, .next, .last (most variables)
    BASE_ONLY = auto()  # base only (team_name, league - team-level, not game-specific)
    BASE_NEXT_ONLY = auto()  # base, .next only (odds_* - no odds for past games)
    LAST_ONLY = auto()  # .last only (score, result - only exist after game ends)


@dataclass(frozen=True)
class VariableDefinition:
    """Complete definition of a template variable."""

    name: str
    category: Category
    suffix_rules: SuffixRules
    extractor: Extractor
    description: str = ""
    examples: dict[str, str] | None = None  # sport -> example value


class VariableRegistry:
    """Singleton registry for all template variables.

    Variables are registered via the @register_variable decorator.
    The registry provides lookup and introspection capabilities.
    """

    _instance: "VariableRegistry | None" = None
    _variables: dict[str, VariableDefinition]

    def __new__(cls) -> "VariableRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._variables = {}
        return cls._instance

    def register(
        self,
        name: str,
        category: Category,
        suffix_rules: SuffixRules,
        extractor: Extractor,
        description: str = "",
        examples: dict[str, str] | None = None,
    ) -> None:
        """Register a variable definition."""
        self._variables[name] = VariableDefinition(
            name=name,
            category=category,
            suffix_rules=suffix_rules,
            extractor=extractor,
            description=description,
            examples=examples,
        )

    def get(self, name: str) -> VariableDefinition | None:
        """Get a variable definition by name."""
        return self._variables.get(name)

    def all_variables(self) -> list[VariableDefinition]:
        """Get all registered variables."""
        return list(self._variables.values())

    def by_category(self, category: Category) -> list[VariableDefinition]:
        """Get all variables in a category."""
        return [v for v in self._variables.values() if v.category == category]

    def count(self) -> int:
        """Get total number of registered variables."""
        return len(self._variables)

    def clear(self) -> None:
        """Clear all registered variables (for testing)."""
        self._variables.clear()

    def to_api_format(self) -> dict:
        """Generate the API response format for /api/variables endpoint.

        Returns format compatible with the frontend template editor.
        Merges examples from variable_examples.py if not defined inline.
        """
        # Import examples from separate file
        from template_resolver.variable_examples import VARIABLE_EXAMPLES

        variables_list = []
        categories_seen = set()

        for var_def in self._variables.values():
            cat_info = CATEGORY_DISPLAY.get(
                var_def.category,
                {"label": var_def.category.name.title(), "icon": "📋"},
            )
            category_name = f"{cat_info['icon']} {cat_info['label']}"
            categories_seen.add(category_name)

            # Convert SuffixRules to available_suffixes list
            suffix_map = {
                SuffixRules.ALL: ["base", "next", "last"],
                SuffixRules.BASE_ONLY: ["base"],
                SuffixRules.BASE_NEXT_ONLY: ["base", "next"],
                SuffixRules.LAST_ONLY: ["last"],
            }
            available_suffixes = suffix_map.get(var_def.suffix_rules, ["base"])

            var_entry = {
                "name": var_def.name,
                "description": var_def.description,
                "category": category_name,
                "icon": cat_info["icon"],
                "available_suffixes": available_suffixes,
            }

            # Add examples - prefer inline, fall back to examples file
            if var_def.examples:
                var_entry["examples_by_sport"] = var_def.examples
            elif var_def.name in VARIABLE_EXAMPLES:
                var_entry["examples_by_sport"] = VARIABLE_EXAMPLES[var_def.name]

            variables_list.append(var_entry)

        # Sort by category then name for consistent output
        variables_list.sort(key=lambda v: (v["category"], v["name"]))

        return {
            "total_variables": len(variables_list),
            "categories": sorted(categories_seen),
            "variables": variables_list,
        }


def register_variable(
    name: str,
    category: Category,
    suffix_rules: SuffixRules = SuffixRules.ALL,
    description: str = "",
    examples: dict[str, str] | None = None,
) -> Callable[[Extractor], Extractor]:
    """Decorator to register a variable extractor.

    Usage:
        @register_variable(
            name="opponent",
            category=Category.IDENTITY,
            suffix_rules=SuffixRules.ALL,
            description="Opponent team name",
            examples={"NBA": "Chicago Bulls", "NFL": "Chicago Bears"},
        )
        def extract_opponent(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
            if not game_ctx or not game_ctx.event:
                return ""
            # ... extraction logic
            return opponent.name
    """

    def decorator(func: Extractor) -> Extractor:
        VariableRegistry().register(
            name, category, suffix_rules, func, description, examples
        )
        return func

    return decorator


def get_registry() -> VariableRegistry:
    """Get the singleton variable registry."""
    return VariableRegistry()
