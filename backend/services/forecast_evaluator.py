"""Forecast vs actual performance evaluation.

Computes MAE, RMSE, MAPE and forecast-accuracy % from previously stored
predictions whose target date has passed. Used by the weekly job and the
forecast-accuracy API.
"""
from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy.orm import Session

from models.waste_prediction import WastePrediction
from models.inventory_item import InventoryItem
from services.forecasting import SALES_TYPES, WASTE_TYPES, daily_series


def compute_metrics(actuals: list[float], predicted: list[float]) -> dict | None:
    pairs = [(a, p) for a, p in zip(actuals, predicted) if a is not None and p is not None]
    if len(pairs) == 0:
        return None
    errors = [a - p for a, p in pairs]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    ape_list = [
        abs(e) / abs(a) * 100 if a else 0.0
        for (a, _p), e in zip(pairs, errors)
    ]
    mape = sum(ape_list) / len(ape_list)
    accuracy = round(max(0.0, 100.0 - mape), 2)
    return {
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "mape": round(mape, 2),
        "accuracy": accuracy,
        "samples": len(pairs),
    }


def _actuals_for(db: Session, owner_id: int, item_id: int, kind: str) -> dict[datetime, float]:
    tx_types = SALES_TYPES if kind == "demand" else WASTE_TYPES
    series = daily_series(db, owner_id, item_id, tx_types, days=120)
    return {day: val for day, val in series.items()}


def evaluate_item(db: Session, owner_id: int, item_id: int, item: InventoryItem | None = None) -> dict | None:
    """Compare recorded predictions vs actuals for one item."""
    preds = (
        db.query(WastePrediction)
        .filter(
            WastePrediction.owner_id == owner_id,
            WastePrediction.item_id == item_id,
            WastePrediction.target_date < datetime.utcnow(),
        )
        .order_by(WastePrediction.target_date.asc())
        .all()
    )
    if not preds:
        return None

    actuals_demand = _actuals_for(db, owner_id, item_id, "demand")
    actuals_waste = _actuals_for(db, owner_id, item_id, "waste")

    dem_actual = [actuals_demand.get(p.target_date.replace(hour=0, minute=0, second=0, microsecond=0), 0.0) for p in preds]
    dem_pred = [p.predicted_demand for p in preds]
    waste_actual = [actuals_waste.get(p.target_date.replace(hour=0, minute=0, second=0, microsecond=0), 0.0) for p in preds]
    waste_pred = [p.predicted_waste for p in preds]

    return {
        "item_id": item_id,
        "item_name": item.name if item else preds[0].item_name,
        "demand": compute_metrics(dem_actual, dem_pred),
        "waste": compute_metrics(waste_actual, waste_pred),
        "samples": len(preds),
        "model_name": preds[0].model_name,
    }


def evaluate_tenant(db: Session, owner_id: int) -> list[dict]:
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == owner_id).all()
    results = []
    for item in items:
        res = evaluate_item(db, owner_id, item.id, item)
        if res:
            results.append(res)
    return results


def tenant_headline(db: Session, owner_id: int) -> dict:
    results = evaluate_tenant(db, owner_id)
    accs = [r["demand"]["accuracy"] for r in results if r.get("demand")]
    rate = len(results)
    if not accs:
        return {"items_evaluated": 0, "overall_accuracy": None, "worst": []}
    worst = sorted(results, key=lambda r: (r.get("demand") or {}).get("accuracy", 101))[:5]
    return {
        "items_evaluated": rate,
        "overall_accuracy": round(sum(accs) / len(accs), 2),
        "worst": [
            {
                "item_id": r["item_id"],
                "item_name": r["item_name"],
                "accuracy": (r.get("demand") or {}).get("accuracy"),
                "mae": (r.get("demand") or {}).get("mae"),
            }
            for r in worst
        ],
    }