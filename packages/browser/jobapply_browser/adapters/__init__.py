"""ATS adapters.

``get_adapter`` maps a detected platform to its adapter; anything unrecognised gets
the deliberately conservative generic one rather than a best guess.
"""

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.ashby import AshbyAdapter
from jobapply_browser.adapters.base import ApplicationAdapter, BaseAdapter
from jobapply_browser.adapters.generic import GenericAdapter
from jobapply_browser.adapters.greenhouse import GreenhouseAdapter
from jobapply_browser.adapters.icims import ICIMSAdapter
from jobapply_browser.adapters.lever import LeverAdapter
from jobapply_browser.adapters.smartrecruiters import SmartRecruitersAdapter
from jobapply_browser.adapters.workday import WorkdayAdapter

ADAPTERS: dict[AtsKind, type[BaseAdapter]] = {
    AtsKind.GREENHOUSE: GreenhouseAdapter,
    AtsKind.LEVER: LeverAdapter,
    AtsKind.ASHBY: AshbyAdapter,
    AtsKind.WORKDAY: WorkdayAdapter,
    AtsKind.ICIMS: ICIMSAdapter,
    AtsKind.SMARTRECRUITERS: SmartRecruitersAdapter,
    AtsKind.GENERIC: GenericAdapter,
}

#: Adapters an operator can disable when a platform changes and breaks automation.
DEFAULT_ENABLED = frozenset(ADAPTERS)


def get_adapter(ats: AtsKind | str, *, enabled: frozenset[AtsKind] | None = None) -> BaseAdapter:
    kind = AtsKind(ats) if not isinstance(ats, AtsKind) else ats
    allowed = enabled if enabled is not None else DEFAULT_ENABLED
    if kind not in ADAPTERS or kind not in allowed:
        return GenericAdapter()
    return ADAPTERS[kind]()


__all__ = [
    "ADAPTERS",
    "DEFAULT_ENABLED",
    "ApplicationAdapter",
    "AshbyAdapter",
    "BaseAdapter",
    "GenericAdapter",
    "GreenhouseAdapter",
    "ICIMSAdapter",
    "LeverAdapter",
    "SmartRecruitersAdapter",
    "WorkdayAdapter",
    "get_adapter",
]
