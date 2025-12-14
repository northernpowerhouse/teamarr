"""V2 Template Resolution Engine.

Provides modular, type-safe template variable resolution.

Usage:
    from template_resolver import TemplateResolver
    from core import TemplateContext, TeamConfig

    resolver = TemplateResolver()
    result = resolver.resolve("{team_name} vs {opponent}", context)

The resolver uses registered variable extractors to resolve placeholders.
Variables are organized by category and support suffix rules (.next, .last).
"""

from template_resolver.registry import (
    Category,
    SuffixRules,
    VariableDefinition,
    VariableRegistry,
    get_registry,
    register_variable,
)
from template_resolver.resolver import TemplateResolver, resolve

__all__ = [
    # Main API
    "TemplateResolver",
    "resolve",
    # Registry
    "Category",
    "SuffixRules",
    "VariableDefinition",
    "VariableRegistry",
    "get_registry",
    "register_variable",
]

# Import all variable modules to register them
# This happens automatically when the package is imported
from template_resolver import variables  # noqa: F401
