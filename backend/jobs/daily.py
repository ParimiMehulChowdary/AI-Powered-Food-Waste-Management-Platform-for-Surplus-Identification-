from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.inventory_item import InventoryItem
from models.category import Category
from models.risk_assessment import RiskAssessment
from models.recommendation import Recommendation
from models.anomaly import Anomaly
from models.surplus_allocation import SurplusAllocation
from models.waste_cause import WasteCause

from services.forecasting import generate_predictions_for_item, utc_now
from services.risk_engine import assess_item, classify
from services.recommendation_engine import generate_for_item, regenerate_for_owner
from services.surplus_engine import allocate_for_item
from services.anomaly_detector import exception_safe_detect
from services.cause_classifier import classify_item
from services.inventory_optimization import optimize_item
from services.notification_service import notify, today_key


def run_for_tenant(db: Session, owner_id: int) -> dict:
    """Daily AI job for one business: predict, assess, detect, recommend, allocate, notify."""
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == owner_id).all()
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == owner_id).all()}

    date_key = today_key()

    predicted = 0
    assessed = 0
    anomalies_saved = 0
    recommendations_saved = 0
    allocations_saved = 0
    causes_saved = 0
    notifications_saved = 0

    # recommendations are regenerated from scratch so the latest data is authoritative
    regenerate_for_owner(db, owner_id)
    db.query(SurplusAllocation).filter(
        SurplusAllocation.owner_id == owner_id,
        SurplusAllocation.status == "pending",
    ).delete()

    for item in items:
        # 1) predictions
        try:
            _rows, forecast = generate_predictions_for_item(db, item, owner_id, horizon_days=7)
            predicted += 1
        except Exception:  # noqa: BLE001
            forecast = None
            predicted += 0

        cat = categories.get(item.category_id)

        # 2) explainable risk assessment
        try:
            if forecast is None:
                from services.forecasting import forecast_item
                forecast = forecast_item(db, item, horizon_days=7)
            assessment = assess_item(db, item, cat, forecast=forecast)
            db.query(RiskAssessment).filter(
                RiskAssessment.owner_id == owner_id, RiskAssessment.item_id == item.id
            ).delete()
            db.add(RiskAssessment(
                owner_id=owner_id,
                item_id=item.id,
                item_name=item.name,
                category_id=item.category_id,
                risk_score=assessment["risk_score"],
                risk_level=assessment["risk_level"],
                factors=assessment["factors"],
                explanation=assessment["explanation"],
                model_name=assessment["model_name"],
                model_version=assessment["model_version"],
                thresholds=assessment["thresholds"],
            ))
            assessed += 1
        except Exception:  # noqa: BLE001
            assessment = None

        # 5) notifications per critical item
        if assessment and assessment["risk_level"] in ("high", "critical"):
            level = assessment["risk_level"].title()
            created = notify(
                db, owner_id, "high_waste_risk", level.lower(),
                f"{level} waste risk for '{item.name}': {assessment['explanation']}",
                item_id=item.id, item_name=item.name,
                source_ref=f"risk:{item.id}", event_date=date_key,
            )
            if created:
                notifications_saved += 1

        if assessment and assessment["risk_level"] == "critical" and assessment.get("days_to_expiry") is not None and assessment["days_to_expiry"] <= 0:
            created = notify(
                db, owner_id, "critical_expiry", "critical",
                f"'{item.name}' is past its expiry date with {item.quantity:g} units still on hand.",
                item_id=item.id, item_name=item.name,
                source_ref=f"expiry:{item.id}", event_date=date_key,
            )
            if created:
                notifications_saved += 1

        # 3) recommendations
        try:
            if forecast and assessment:
                reorder = optimize_item(item, forecast, cat)
                recs = generate_for_item(item, assessment, forecast=forecast, category=cat, reorder_suggestion=reorder)
                for r in recs:
                    db.add(Recommendation(
                        owner_id=owner_id, item_id=item.id, item_name=item.name,
                        **r,
                    ))
                    recommendations_saved += 1
        except Exception:  # noqa: BLE001
            pass

        # 4) surplus allocation
        try:
            if forecast and assessment:
                alloc = allocate_for_item(db, item, forecast, assessment, category=cat)
                if alloc:
                    db.add(SurplusAllocation(
                        owner_id=owner_id,
                        item_id=item.id,
                        item_name=item.name,
                        surplus_quantity=alloc["surplus_quantity"],
                        safe_period_days=alloc["safe_period_days"],
                        urgency=alloc["urgency"],
                        allocation_type=alloc["allocation_type"],
                        suggested_partner=alloc["suggested_partner"],
                        reason=alloc["reason"],
                    ))
                    allocations_saved += 1
                    n1 = notify(
                        db, owner_id, "predicted_surplus", "high" if alloc["urgency"] <= 2 else "medium",
                        f"{alloc['surplus_quantity']:g} units of '{item.name}' are forecast surplus within {alloc['safe_period_days']} day(s). Recommended {alloc['allocation_type']}.",
                        item_id=item.id, item_name=item.name,
                        source_ref=f"surplus:{item.id}", event_date=date_key,
                    )
                    if n1:
                        notifications_saved += 1
                    if alloc["allocation_type"] == "donation":
                        n2 = notify(
                            db, owner_id, "donation_opportunity", "medium",
                            f"{alloc['surplus_quantity']:g} units of '{item.name}' are suitable for donation.",
                            item_id=item.id, item_name=item.name,
                            source_ref=f"donate:{item.id}", event_date=date_key,
                        )
                        if n2:
                            notifications_saved += 1
        except Exception:  # noqa: BLE001
            pass

        # 6) waste cause
        try:
            cause = classify_item(db, item, cat)
            if cause:
                db.add(WasteCause(
                    owner_id=owner_id, item_id=item.id, item_name=item.name,
                    cause=cause["cause"], explanation=cause["explanation"],
                    confidence=cause["confidence"],
                    period_start=utc_now() - timedelta(days=30),
                    period_end=utc_now(),
                ))
                causes_saved += 1
        except Exception:  # noqa: BLE001
            pass

    # 7) anomaly detection
    for anomaly_dict in exception_safe_detect(db, owner_id, date_key):
        exists = db.query(Anomaly).filter(Anomaly.dedupe_key == anomaly_dict["dedupe_key"]).first()
        if exists:
            continue
        db.add(Anomaly(**anomaly_dict))
        anomalies_saved += 1
        if anomaly_dict["severity"] in ("high", "critical"):
            a_type = anomaly_dict["anomaly_type"].replace("_", " ")
            notify(
                db, owner_id, "unusual_waste" if "waste" in anomaly_dict["anomaly_type"] else "demand_anomaly" if "demand" in anomaly_dict["anomaly_type"] or "sales" in anomaly_dict["anomaly_type"] else "overstock",
                anomaly_dict["severity"],
                f"{a_type} detected: {anomaly_dict['explanation']}",
                item_id=anomaly_dict.get("item_id"),
                item_name=anomaly_dict.get("item_name"),
                source_ref=f"anom:{anomaly_dict['dedupe_key']}",
                event_date=date_key,
            )
            notifications_saved += 1

    db.commit()

    return {
        "owner_id": owner_id,
        "items_scanned": len(items),
        "predictions": predicted,
        "risk_assessments": assessed,
        "anomalies": anomalies_saved,
        "recommendations": recommendations_saved,
        "surplus_allocations": allocations_saved,
        "waste_causes": causes_saved,
        "notifications": notifications_saved,
    }


def run_daily(db: Session) -> dict:
    from models.user import User
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    results = []
    for user in users:
        try:
            results.append(run_for_tenant(db, user.id))
        except Exception as exc:  # noqa: BLE001
            results.append({"owner_id": user.id, "error": str(exc)})
            db.rollback()
    return {"status": "ok", "tenants": len(users), "results": results}