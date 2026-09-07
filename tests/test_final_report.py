import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_final_report_evidence_is_machine_readable_and_complete_enough_to_summarize() -> None:
    evidence = json.loads((ROOT / "docs" / "FINAL_TEST_EVIDENCE.json").read_text(encoding="utf-8"))

    assert evidence["schema_version"] == 1
    assert evidence["status"] in {"IN_PROGRESS", "FINAL_STAGE_7", "FINAL"}
    assert evidence["provenance"]["dataset"]["sha256"]
    assert evidence["automated_checks"]["python_tests"]["status"] == "PASS"
    assert {profile["name"] for profile in evidence["mt5_real_tick_profiles"]} == {
        "capital_200",
        "capital_300",
    }
    required_metrics = {
        "attempts",
        "accepted",
        "rejected",
        "net_realized_pnl_usd",
        "realized_gross_loss_usd",
        "sl_loosen_violations",
        "final_exposure",
        "lifecycle_failures",
    }
    for profile in evidence["mt5_real_tick_profiles"]:
        assert required_metrics <= profile.keys()
        assert profile["attempts"] == profile["accepted"] + profile["rejected"]
        assert profile["pullback_tp"] == {
            "extensions": 1,
            "restores": 1,
            "market_closes": 0,
            "rejections": 0,
        }
    restart = evidence["safety_evidence"]["same_day_restart_runtime"]
    assert restart["status"] == "PASS"
    assert restart["attempts"] == restart["maximum_observed_positions"] == 0
    assert evidence["safety_evidence"]["symbol_specification"]["status"] == "PASS"
    multiday = evidence["mt5_multiday_engineering"]
    assert multiday["status"] == "PASS"
    assert multiday["attempts"] == multiday["accepted"] + multiday["rejected"]
    assert multiday["final_exposure"] == multiday["lifecycle_failures"] == 0
    attribution = evidence["signal_attribution"]["multiday_attempt_accepted_rejected"]
    assert attribution["reversal_normal"] == [86, 86, 0]
    assert attribution["reversal_high"] == [26, 26, 0]


def test_visual_leader_gate_is_replaced_by_reusable_final_report() -> None:
    todo = (ROOT / "docs" / "TODO.md").read_text(encoding="utf-8")
    rules = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")

    assert "## 7) تایید بصری رهبر پروژه" not in todo
    assert "## 7) گزارش جامع نهایی تست" in todo
    assert "FINAL_TEST_REPORT" in rules
    assert "درخواست گزارش مجدد نباید باعث اجرای دوباره MT5 شود" in rules
