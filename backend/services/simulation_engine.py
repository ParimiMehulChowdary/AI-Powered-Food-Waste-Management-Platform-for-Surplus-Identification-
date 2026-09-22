"""What-if simulation engine.

Estimates the outcome of business decisions (purchase quantity, discount,
expected demand, donation quantity) using the existing forecasting logic.
All results are labelled as simulations/estimates — never as actuals.
"""
from __future__ import annotations

from models.inventory_item import InventoryItem


def validate_params(params: dict) -> None:
    if not isinstance(params.get("current_stock", 0.0), (int, float)) or params.get("current_stock", 0) < 0:
        raise ValueError("current_stock must be a non-negative number")
    for key in ("purchase_quantity", "donation_quantity"):
        if params.get(key, 0) < 0:
            raise ValueError(f"{key} must be non-negative")
    pct = params.get("discount_pct", 0)
    if not isinstance(pct, (int, float)) or not (0 <= pct <= 100):
        raise ValueError("discount_pct must be between 0 and 100")
    if params.get("expected_demand", 0) < 0:
        raise ValueError("expected_demand must be non-negative")


def run_simulation(item: InventoryItem | None, forecast: dict | None, params: dict) -> dict:
    """Run a simulation and return labelled estimates.

    ``params``: current_stock, purchase_quantity, discount_pct, expected_demand,
    donation_quantity, horizon_days, cost_per_unit (optional override).
    """
    validate_params(params)

    cost = float(params.get("cost_per_unit", item.cost_per_unit if item else 0.0) or 0.0)
    horizon = int(params.get("horizon_days", 7))
    current_stock = float(params.get("current_stock", item.quantity if item else 0.0))
    purchase = float(params.get("purchase_quantity", 0.0))
    donation = float(params.get("donation_quantity", 0.0))
    discount_pct = float(params.get("discount_pct", 0.0))

    expected_demand = params.get("expected_demand")
    if expected_demand is None and forecast:
        expected_demand = forecast.get("total_demand", 0.0)
    if expected_demand is None:
        expected_demand = 0.0
    expected_demand = float(expected_demand)

    # Conservative demand lift from discount (elasticity assumed 0.5 unless overridden)
    elasticity = float(params.get("elasticity", 0.5))
    lift = discount_pct / 100.0 * elasticity
    effective_demand = expected_demand * (1 + lift)

    # Baseline (before changes): stock clears against unchanged demand
    baseline_remaining = current_stock - expected_demand
    baseline_waste = max(baseline_remaining, 0.0)
    baseline_surplus = max(baseline_remaining, 0.0)
    baseline_waste_value = baseline_waste * cost

    stock_after_purchase = current_stock + purchase
    simulated_remaining = stock_after_purchase - effective_demand - donation
    simulated_waste = max(simulated_remaining, 0.0)
    simulated_surplus = max(simulated_remaining, 0.0)
    simulated_waste_value = simulated_waste * cost
    donated_value = donation * cost

    potential_savings = max(baseline_waste_value - simulated_waste_value, 0.0)

    return {
        "is_simulation": True,
        "label": "Simulation result — an estimate, not actual data.",
        "item_id": item.id if item else None,
        "item_name": item.name if item else params.get("item_name"),
        "horizon_days": horizon,
        "baseline": {
            "stock": round(current_stock, 2),
            "expected_demand": round(expected_demand, 2),
            "remaining": round(baseline_remaining, 2),
            "surplus": round(baseline_surplus, 2),
            "waste": round(baseline_waste, 2),
            "waste_value": round(baseline_waste_value, 2),
        },
        "simulated": {
            "stock_after_purchase": round(stock_after_purchase, 2),
            "effective_demand": round(effective_demand, 2),
            "remaining": round(simulated_remaining, 2),
            "surplus": round(simulated_surplus, 2),
            "waste": round(simulated_waste, 2),
            "waste_value": round(simulated_waste_value, 2),
            "donated_quantity": round(donation, 2),
            "donated_value": round(donated_value, 2),
        },
        "potential_savings": round(potential_savings, 2),
        "summary": (
            f"Reducing next purchase by {purchase:g} units and discounting {discount_pct:g}% "
            f"with {donation:g} units donated changes predicted surplus from "
            f"{baseline_surplus:g} to {simulated_surplus:g} units and predicted waste from "
            f"{baseline_waste:g} to {simulated_waste:g} units "
            f"(${potential_savings:,.2f} potential savings)."
        ),
    }