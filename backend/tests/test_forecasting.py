from services.forecasting import (
    exponential_smoothing,
    moving_average,
    linear_trend,
    choose_method,
    forecast_kind,
    MIN_POINTS_FOR_ML,
)
from services.forecast_evaluator import compute_metrics


def test_exponential_smoothing_matches_expected_formula():
    # alpha 1.0 -> copy of last value (all weight on most recent)
    assert exponential_smoothing([1, 2, 3], alpha=1.0) == 3
    # constant series -> same constant
    assert exponential_smoothing([5, 5, 5, 5], alpha=0.3) == 5


def test_moving_average_window():
    assert moving_average([1, 2, 3, 4, 5], window=5) == 3.0
    assert moving_average([2, 4, 6], window=3) == 4.0


def test_linear_trend_steps_up():
    # strictly increasing 1,2,3 -> next step extrapolation > 3
    assert linear_trend([1, 2, 3]) > 3


def test_choose_method_falls_back_when_too_little_data():
    assert choose_method([10]) == "fallback"
    assert choose_method([]) == "fallback"


def test_forecast_kind_returns_no_fabrication_for_empty_history(db):
    from models.inventory_item import InventoryItem
    from services.forecasting import SALES_TYPES
    item = InventoryItem(owner_id=1, name="Ghost", quantity=0, unit="units")
    db.add(item)
    db.commit()
    db.refresh(item)
    result = forecast_kind(db, 1, item.id, SALES_TYPES)
    assert result["is_fallback"] is True
    assert result["confidence"] == 0.0
    assert result["model_name"] == "rule_based_fallback"


def test_compute_metrics_perfect_forecast():
    metrics = compute_metrics([10, 20, 30], [10, 20, 30])
    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["accuracy"] == 100.0


def test_compute_metrics_known_errors():
    metrics = compute_metrics([10, 20, 30], [12, 18, 30])
    assert abs(metrics["mae"] - 4.0 / 3) < 1e-3
    assert abs(metrics["rmse"] - 1.633) < 1e-3
    assert metrics["accuracy"] == 90.0