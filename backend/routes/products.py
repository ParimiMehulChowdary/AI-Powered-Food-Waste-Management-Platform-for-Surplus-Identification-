from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.inventory_item import InventoryItem
from models.category import Category
from models.waste_prediction import WastePrediction
from models.risk_assessment import RiskAssessment
from models.recommendation import Recommendation
from models.anomaly import Anomaly
from security import get_current_user
from services import risk_engine, inventory_optimization, forecasting, forecast_evaluator

router = APIRouter(prefix="/api/products", tags=["products"])


def _get_item(db: Session, user: User, item_id: int) -> InventoryItem:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.owner_id == user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return item


def _category(db: Session, user: User, item: InventoryItem):
    if not item.category_id:
        return None, None
    cat = db.query(Category).filter(Category.id == item.category_id, Category.owner_id == user.id).first()
    return cat, (cat.name if cat else None)


@router.get("/{item_id}/forecast")
def product_forecast(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _get_item(db, user, item_id)
    return _forecast_payload(db, user, item)


def _forecast_payload(db: Session, user: User, item: InventoryItem) -> dict:
    stored = db.query(WastePrediction).filter(
        WastePrediction.owner_id == user.id,
        WastePrediction.item_id == item.id,
    ).order_by(WastePrediction.target_date.asc()).all()

    if stored:
        # rows of one run are inserted microseconds apart; bucket by hour so the
        # whole latest run is returned, not just the single latest row.
        buckets: dict[str, list] = {}
        for p in stored:
            key = p.prediction_date.replace(tzinfo=None)
            buckets.setdefault(key.strftime("%Y-%m-%d %H"), []).append(p)
        latest_key = max(buckets)
        active = buckets[latest_key]
        total_demand = sum(p.predicted_demand for p in active)
        return {
            "item_id": item.id,
            "item_name": item.name,
            "days_to_expiry": _days_left(item),
            "stock": item.quantity,
            "forecast": [
                {
                    "target_date": p.target_date,
                    "predicted_demand": p.predicted_demand,
                    "predicted_waste": p.predicted_waste,
                    "predicted_surplus": p.predicted_surplus,
                    "waste_probability": p.waste_probability,
                    "waste_risk_level": p.waste_risk_level,
                    "confidence": p.confidence,
                    "model_name": p.model_name,
                    "is_fallback": p.is_fallback,
                    "expected_waste_value": p.expected_waste_value,
                }
                for p in active
            ],
            "total_demand": round(total_demand, 2),
            "total_waste": round(sum(p.predicted_waste for p in active), 2),
            "total_surplus": round(max(item.quantity - total_demand, 0), 2),
        }

    result = forecasting.forecast_item(db, item, horizon_days=7)
    return {
        "item_id": item.id,
        "item_name": item.name,
        "days_to_expiry": result.get("days_to_expiry"),
        "stock": item.quantity,
        "forecast": [
            {
                "target_date": t["target_date"],
                "predicted_demand": t["predicted_demand"],
                "predicted_waste": t["predicted_waste"],
                "predicted_surplus": t["predicted_surplus"],
                "waste_probability": t["waste_probability"],
                "waste_risk_level": t["waste_risk_level"],
                "confidence": result["confidence"],
                "model_name": result["model_name"],
                "is_fallback": result["is_fallback"],
                "expected_waste_value": t["expected_waste_value"],
            }
            for t in result["targets"]
        ],
        "total_demand": result["total_demand"],
        "total_waste": result["total_waste"],
        "total_surplus": result["total_surplus"],
        "live_computed": True,
    }


@router.get("/{item_id}/risk")
def product_risk(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _get_item(db, user, item_id)
    cat, cat_name = _category(db, user, item)

    forecast_result = forecasting.forecast_item(db, item, horizon_days=7)
    assessment = risk_engine.assess_item(db, item, cat, forecast=forecast_result)

    stored_assessment = db.query(RiskAssessment).filter(
        RiskAssessment.owner_id == user.id,
        RiskAssessment.item_id == item.id,
    ).order_by(RiskAssessment.created_at.desc()).first()

    recommendations = db.query(Recommendation).filter(
        Recommendation.owner_id == user.id,
        Recommendation.item_id == item.id,
        Recommendation.status == "pending",
    ).order_by(Recommendation.priority.asc()).all()

    anomalies = db.query(Anomaly).filter(
        Anomaly.owner_id == user.id,
        Anomaly.item_id == item.id,
        Anomaly.is_resolved == False,  # noqa: E712
    ).order_by(Anomaly.detected_at.desc()).limit(20).all()

    reorder = inventory_optimization.optimize_item(item, forecast_result, cat)

    accuracy = forecast_evaluator.evaluate_item(db, user.id, item.id, item)

    forecast = _forecast_payload(db, user, item)

    return {
        "product": {
            "id": item.id,
            "name": item.name,
            "sku": item.sku,
            "barcode": item.barcode,
            "category_id": item.category_id,
            "category_name": cat_name,
            "perishability_risk": cat.perishability_risk if cat else None,
            "storage_requirement": cat.storage_requirement if cat else None,
            "unit": item.unit,
            "quantity": item.quantity,
            "cost_per_unit": item.cost_per_unit,
            "expiry_date": item.expiry_date,
            "days_to_expiry": _days_left(item),
            "storage_location": item.storage_location,
            "supplier": item.supplier,
            "created_at": item.created_at,
        },
        "risk": {
            "risk_score": assessment["risk_score"],
            "risk_level": assessment["risk_level"],
            "factors": assessment["factors"],
            "explanation": assessment["explanation"],
            "model_name": assessment["model_name"],
            "thresholds": assessment["thresholds"],
            "stored_at": stored_assessment.created_at if stored_assessment else None,
        },
        "forecast": forecast,
        "recommendations": [
            {
                "id": r.id, "recommendation_type": r.recommendation_type,
                "recommended_quantity": r.recommended_quantity, "priority": r.priority,
                "reason": r.reason, "expected_benefit": r.expected_benefit, "deadline": r.deadline,
            }
            for r in recommendations
        ],
        "anomalies": [
            {
                "id": a.id, "anomaly_type": a.anomaly_type, "severity": a.severity,
                "detected_value": a.detected_value, "expected_value": a.expected_value,
                "explanation": a.explanation, "detected_at": a.detected_at,
            }
            for a in anomalies
        ],
        "reorder": reorder,
        "forecast_accuracy": accuracy,
        "historical_sales": _history(db, user, item, "sale"),
        "historical_waste": _history(db, user, item, "disposal"),
    }


def _days_left(item: InventoryItem):
    from services.risk_service import days_to_expiry
    return days_to_expiry(item.expiry_date) if item.expiry_date else None


def _history(db: Session, user: User, item: InventoryItem, tx_type: str) -> list[dict]:
    from models.transaction import Transaction
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.owner_id == user.id,
            Transaction.item_id == item.id,
            Transaction.transaction_type == tx_type,
        )
        .order_by(Transaction.transaction_date.asc())
        .all()
    )
    out = []
    seen = {}
    for tx in rows:
        day = (tx.transaction_date or item.created_at).strftime("%Y-%m-%d")
        seen[day] = seen.get(day, 0.0) + (tx.quantity or 0.0)
    for day in sorted(seen):
        out.append({"date": day, "quantity": round(seen[day], 2)})
    return out