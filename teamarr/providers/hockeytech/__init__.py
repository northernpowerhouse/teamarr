"""HockeyTech provider for CHL leagues and more.

Provides access to OHL, WHL, QMJHL, AHL, PWHL, USHL via the HockeyTech API
that powers official league websites.
"""

from teamarr.providers.hockeytech.client import HockeyTechClient
from teamarr.providers.hockeytech.provider import HockeyTechProvider

__all__ = ["HockeyTechClient", "HockeyTechProvider"]
