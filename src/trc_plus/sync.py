"""Dry-run synchronization planning.

Process access is intentionally not implemented until a verified, build-specific
address profile is available.
"""

from collections.abc import Mapping

from .models import PlayerData, SyncChange, SyncPlan


def build_dry_run_plan(
    source: PlayerData,
    target_attributes: Mapping[str, int],
) -> SyncPlan:
    """Compare normalized source values with target values without writing memory."""

    changes: list[SyncChange] = []
    warnings: list[str] = []

    for field, new_value in source.attributes.items():
        if not isinstance(new_value, int):
            warnings.append(f"Skipped {field}: value is not an integer")
            continue
        if not 0 <= new_value <= 99:
            warnings.append(f"Skipped {field}: value is outside the 0-99 range")
            continue

        old_value = target_attributes.get(field)
        if old_value != new_value:
            changes.append(
                SyncChange(
                    player_id=source.player_id,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                )
            )

    return SyncPlan(changes=tuple(changes), warnings=tuple(warnings))
