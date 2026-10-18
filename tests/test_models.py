from trc_plus.models import PlayerData
from trc_plus.sync import build_dry_run_plan


def test_dry_run_plan_contains_only_changed_valid_attributes() -> None:
    source = PlayerData(
        player_id="trc-001",
        name="Example Player",
        attributes={"speed": 85, "strength": 100, "three_point": "85"},  # type: ignore[arg-type]
    )

    plan = build_dry_run_plan(source, {"speed": 80})

    assert [(change.field, change.new_value) for change in plan.changes] == [("speed", 85)]
    assert "strength" in " ".join(plan.warnings)
    assert "three_point" in " ".join(plan.warnings)
