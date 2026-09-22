from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.inventory_item import InventoryItem
from models.forecast_performance import ForecastPerformance
from services.forecast_evaluator import evaluate_item
from services.notification_service import notify, today_key


def run_weekly(db: Session) -> dict:
    from models.user import User
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    results = []
    for user in users:
        results.append(run_for_tenant(db, user.id))
    return {"status": "ok", "tenants": len(users), "details": results}


def run_for_tenant(db: Session, owner_id: int) -> dict:
    """Weekly job: recompute forecast accuracy and store model performance.

    Also refreshes forecast-vs-actual analytics by evaluating every item with
    at least one past target-date prediction.
    """
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == owner_id).all()
    stored = 0
    worst_accuracy = None
    low_performers = []

    from services.forecast_evaluator import evaluate_tenant
    evaluations = evaluate_tenant(db, owner_id)

    # replace the previous week's performance snapshot
    db.query(ForecastPerformance).filter(ForecastPerformance.owner_id == owner_id).delete()

    for ev in evaluations:
        demand = ev.get("demand") or {}
        waste = ev.get("waste") or {}
        db.add(ForecastPerformance(
            owner_id=owner_id,
            item_id=ev["item_id"],
            item_name=ev.get("item_name"),
            model_name=ev.get("model_name", "total"),
            mae=demand.get("mae"),
            rmse=demand.get("rmse"),
            mape=demand.get("mape"),
            accuracy=demand.get("accuracy"),
            samples=ev.get("samples", 0),
            window_start=datetime.utcnow() - timedelta(days=30),
            window_end=datetime.utcnow(),
        ))
        stored += 1
        acc = demand.get("accuracy")
        if acc is not None and (worst_accuracy is None or acc < worst_accuracy):
            worst_accuracy = acc
        if acc is not None and acc < 60:
            low_performers.append((ev.get("item_name"), acc))

    db.commit()

    if low_performers:
        bad = ", ".join(f"{name} ({acc:.0f}%)" for name, acc in low_performers[:3])
        notify(
            db, owner_id, "model_performance", "medium",
            f"Forecast accuracy is below 60% for: {bad}. Review demand patterns for these items.",
            event_date=today_key(),
        )
        db.commit()

    return {
        "owner_id": owner_id,
        "items_evaluated": stored,
        "worst_accuracy": worst_accuracy,
        "low_performers": [{"item_name": n, "accuracy": a} for n, a in low_performers],
    }