import pytest
from pydantic import ValidationError

from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs


@pytest.mark.parametrize(
    "settings",
    [
        {"penetration": 0},
        {"penetration": -0.1},
        {"preclose_minutes": 0},
        {"preclose_minutes": 60.01},
        {"risk_percent": 0},
        {"risk_percent": 100},
        {"risk_mode": "net", "risk_percent": -1},
        {"daily_loss_override": True, "daily_loss_percent": 0},
        {"daily_loss_override": True, "daily_loss_percent": 100},
        {"qa_discovery": True, "qa_capital": 0},
    ],
)
def test_visible_oninit_rejects_invalid_enabled_parameters(settings):
    with pytest.raises(ValidationError):
        RobustInputs(**settings)


@pytest.mark.parametrize(
    "settings",
    [
        {"penetration": 0.00001},
        {"preclose_minutes": 60},
        {"risk_mode": "off", "risk_percent": 0},
        {"risk_mode": "off", "risk_percent": 100},
        {"daily_loss_override": False, "daily_loss_percent": 0},
        {"daily_loss_override": False, "daily_loss_percent": 100},
        {"qa_discovery": False, "qa_capital": 0},
        {"qa_discovery": False, "qa_capital": -1},
    ],
)
def test_visible_oninit_accepts_boundaries_and_ignored_disabled_parameters(settings):
    assert RobustInputs(**settings).model_dump().items() >= settings.items()
