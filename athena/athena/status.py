"""RAM accounting for `/api/status`, measured against the budget table in ATHENA.md.

Convention from the spec: the numbers in the budget table are design *targets*, to be
sanity-checked against measured reality and corrected — never silently exceeded. This
module is how the daemon reports the comparison, so the check is a glance at Aegis rather
than an archaeology session with Activity Monitor.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import psutil

GB = 1024**3

# ATHENA.md, "Hardware profile — 16 GB Apple Silicon". Targets, in GB.
BUDGET_GB: dict[str, float] = {
    "daemon": 0.5,  # daemon + FastAPI + wake word + VAD, always resident
    "whisper": 1.0,  # small.en, ACTIVE/SERIOUS only (lazy) — phase 2
    "brain": 5.0,  # Ollama 8B q4, ACTIVE/SERIOUS + 10 min grace
    "embeddings": 0.5,  # on demand — phase 4
    "warm_total": 7.0,  # talking
    "dormant_total": 0.6,
}


@dataclass(frozen=True)
class RamReport:
    daemon_gb: float
    models_gb: float
    total_gb: float
    budget_gb: float
    within_budget: bool
    machine_total_gb: float
    machine_available_gb: float
    detail: dict[str, Any]


def daemon_rss_gb() -> float:
    """RSS of the daemon plus any child processes it spawned (uvicorn workers, etc.)."""
    proc = psutil.Process(os.getpid())
    total = proc.memory_info().rss
    for child in proc.children(recursive=True):
        try:
            total += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total / GB


def build_report(resident_models: list[dict[str, Any]], state: str) -> RamReport:
    """Compare live footprint against the budget for the current state."""
    daemon_gb = daemon_rss_gb()
    models_gb = sum(float(m.get("size_bytes") or 0) for m in resident_models) / GB
    total = daemon_gb + models_gb
    budget = BUDGET_GB["dormant_total"] if state == "DORMANT" else BUDGET_GB["warm_total"]
    vm = psutil.virtual_memory()
    return RamReport(
        daemon_gb=round(daemon_gb, 3),
        models_gb=round(models_gb, 3),
        total_gb=round(total, 3),
        budget_gb=budget,
        within_budget=total <= budget,
        machine_total_gb=round(vm.total / GB, 2),
        machine_available_gb=round(vm.available / GB, 2),
        detail={
            "budget_table_gb": BUDGET_GB,
            "resident_models": resident_models,
            "note": (
                "Budget compared against dormant_total in DORMANT, warm_total otherwise. "
                "Model footprint is what Ollama reports resident, not what it reserved."
            ),
        },
    )


class ErrorLog:
    """A tiny ring buffer of recent errors, surfaced by /api/status.

    Local-only, no telemetry of any kind (security invariant 8).
    """

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self._items: list[dict[str, Any]] = []

    def record(self, where: str, message: str) -> None:
        self._items.append({"at": time.time(), "where": where, "message": message[:500]})
        del self._items[: max(0, len(self._items) - self.limit)]

    def recent(self) -> list[dict[str, Any]]:
        return list(reversed(self._items))
