"""Shared data models for the TRC-to-NBA 2K27 sync pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlayerData:
    """Normalized player data ready for validation and mapping."""

    player_id: str
    name: str
    attributes: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncChange:
    """One field change in a dry-run or execution plan."""

    player_id: str
    field: str
    old_value: Any
    new_value: Any


@dataclass(frozen=True)
class SyncPlan:
    """Validated changes that can be reviewed before execution."""

    changes: tuple[SyncChange, ...]
    warnings: tuple[str, ...] = ()
