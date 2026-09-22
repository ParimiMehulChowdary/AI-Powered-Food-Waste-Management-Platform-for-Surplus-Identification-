import pytest

from services.simulation_engine import run_simulation, validate_params


def test_simulation_basic_math():
    result = run_simulation(item=None, forecast=None, params={
        "current_stock": 100,
        "purchase_quantity": 0,
        "expected_demand": 60,
        "discount_pct": 0,
        "donation_quantity": 0,
        "horizon_days": 7,
        "cost_per_unit": 2.0,
    })
    assert result["is_simulation"] is True
    assert result["baseline"]["waste"] == 40
    assert result["baseline"]["waste_value"] == 80
    assert result["simulated"]["waste"] == 40
    assert result["potential_savings"] == 0.0


def test_simulation_donation_reduces_waste():
    result = run_simulation(item=None, forecast=None, params={
        "current_stock": 100,
        "donation_quantity": 30,
        "expected_demand": 60,
        "cost_per_unit": 1.0,
    })
    assert result["simulated"]["waste"] == 10
    assert result["baseline"]["waste"] == 40
    assert result["simulated"]["donated_quantity"] == 30
    assert "simulation" in result["label"].lower()


def test_simulation_labels_results_as_estimates():
    result = run_simulation(item=None, forecast=None, params={
        "current_stock": 10, "expected_demand": 5,
    })
    assert "simulation" in result["label"].lower()
    assert "not actual" in result["label"].lower()


def test_simulation_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        validate_params({"discount_pct": 150})
    with pytest.raises(ValueError):
        validate_params({"purchase_quantity": -5})
    with pytest.raises(ValueError):
        validate_params({"current_stock": -1})