from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.user import User
from models.category import Category
from models.inventory_item import InventoryItem
from models.transaction import Transaction
from models.waste_alert import WasteAlert
from models.recommendation import Recommendation
from models.anomaly import Anomaly
from models.surplus_allocation import SurplusAllocation
from models.notification import Notification
from security import get_current_user
from services import analytics_service
from services.risk_service import (
    compute_risk_score, days_to_expiry, risk_level, expiration_status,
    build_alert_message, build_shelf_life_breach_message, build_low_stock_message,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id).all()
    categories = db.query(Category).filter(Category.owner_id == user.id).all()
    cat_map = {c.id: c for c in categories}

    total_value = 0.0
    total_units = 0
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    expiring = []
    expired = []
    surplus_candidates = []
    category_breakdown = {}

    for item in items:
        cat = cat_map.get(item.category_id)
        days_left = days_to_expiry(item.expiry_date)
        risk = compute_risk_score(
            days_left, item.quantity,
            perishability_risk=cat.perishability_risk if cat else "medium",
            storage_requirement=cat.storage_requirement if cat else "ambient",
            waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
        )
        lvl = risk_level(risk)
        total_units += item.quantity
        total_value += item.quantity * item.cost_per_unit
        risk_counts[lvl] += 1

        status = expiration_status(days_left)
        if status == "expired":
            expired.append({
                "id": item.id, "name": item.name, "quantity": item.quantity,
                "days_to_expiry": days_left, "risk_score": risk, "risk_level": lvl,
            })
        elif status in ("expiring_soon", "expiring"):
            expiring.append({
                "id": item.id, "name": item.name, "quantity": item.quantity,
                "days_to_expiry": days_left, "risk_score": risk, "risk_level": lvl,
                "message": build_alert_message(item.name, status, days_left),
            })
        if days_left is not None and 0 <= days_left <= 3 and item.quantity > 0:
            surplus_candidates.append({
                "id": item.id, "name": item.name, "quantity": item.quantity,
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                "risk_score": risk,
            })

        cat_name = cat.name if cat else "Uncategorized"
        cat_data = category_breakdown.setdefault(cat_name, {"count": 0, "units": 0.0, "risk": 0.0})
        cat_data["count"] += 1
        cat_data["units"] += item.quantity
        cat_data["risk"] += risk

    for data in category_breakdown.values():
        if data["count"]:
            data["risk"] = round(data["risk"] / data["count"], 1)

    expiring.sort(key=lambda x: x["days_to_expiry"] or 999)
    expired.sort(key=lambda x: (x["days_to_expiry"] or 0))

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    donations_total = db.query(func.coalesce(func.sum(Transaction.quantity), 0.0)).filter(
        Transaction.owner_id == user.id,
        Transaction.transaction_type == "donation",
        Transaction.transaction_date >= week_ago,
    ).scalar()
    disposal_total = db.query(func.coalesce(func.sum(Transaction.quantity), 0.0)).filter(
        Transaction.owner_id == user.id,
        Transaction.transaction_type == "disposal",
        Transaction.transaction_date >= week_ago,
    ).scalar()

    recent_txs = db.query(Transaction).filter(
        Transaction.owner_id == user.id
    ).order_by(Transaction.transaction_date.desc()).limit(10).all()

    active_alerts_count = db.query(func.count(WasteAlert.id)).filter(
        WasteAlert.owner_id == user.id, WasteAlert.is_resolved == False
    ).scalar() or 0

    return {
        "summary": {
            "total_items": len(items),
            "total_units": round(total_units, 2),
            "total_value": round(total_value, 2),
            "donations_week": round(donations_total, 2),
            "disposal_week": round(disposal_total, 2),
            "active_alerts": active_alerts_count,
        },
        "risk_counts": risk_counts,
        "expiring": expiring[:10],
        "expired": expired[:10],
        "surplus_candidates": surplus_candidates[:10],
        "category_breakdown": category_breakdown,
        "recent_transactions": [
            {
                "id": t.id, "item_name": t.item_name, "transaction_type": t.transaction_type,
                "quantity": t.quantity, "unit": t.unit, "transaction_date": t.transaction_date.isoformat(),
                "reference": t.reference,
            }
            for t in recent_txs
        ],
    }


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return saved alerts, refreshing from current inventory state first."""
    return _regenerate_alerts(db, user)


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = db.query(WasteAlert).filter(WasteAlert.id == alert_id, WasteAlert.owner_id == user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_resolved = True
    db.commit()
    return {"detail": "Alert resolved"}


@router.get("/stored-alerts")
def stored_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(WasteAlert).filter(WasteAlert.owner_id == user.id).all()
    return [
        {
            "id": a.id, "item_id": a.item_id, "item_name": a.item_name,
            "alert_type": a.alert_type, "risk_score": a.risk_score,
            "days_to_expiry": a.days_to_expiry, "message": a.message,
            "is_resolved": a.is_resolved, "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


def _regenerate_alerts(db: Session, user: User):
    """Recompute alerts from current inventory state (webhook-style check)."""
    db.query(WasteAlert).filter(WasteAlert.owner_id == user.id).delete()
    alerts = []

    from models.business_settings import BusinessSettings

    settings = db.query(BusinessSettings).filter(BusinessSettings.owner_id == user.id).first()

    items = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id).all()
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == user.id).all()}

    low_stock_threshold = settings.low_stock_threshold if settings else 5.0
    breach_enabled = bool(settings.shelf_life_breach_enabled) if settings else True
    low_stock_enabled = bool(settings.low_stock_alert_enabled) if settings else True

    for item in items:
        cat = categories.get(item.category_id)
        days_left = days_to_expiry(item.expiry_date)
        risk = compute_risk_score(
            days_left, item.quantity,
            perishability_risk=cat.perishability_risk if cat else "medium",
            storage_requirement=cat.storage_requirement if cat else "ambient",
            waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
        )
        status = expiration_status(days_left)
        message = build_alert_message(item.name, status, days_left)
        if status in ("expired", "expiring_soon") and message:
            alert = WasteAlert(
                owner_id=user.id, item_id=item.id, item_name=item.name,
                alert_type="expiry_soon", risk_score=risk,
                days_to_expiry=days_left or 0, message=message,
            )
            db.add(alert)
            alerts.append(alert)

        if (
            breach_enabled
            and cat
            and cat.default_shelf_life_days
            and item.created_at
        ):
            days_in_stock = (datetime.utcnow() - item.created_at.replace(tzinfo=None)).days
            if days_in_stock >= cat.default_shelf_life_days and not (days_left is not None and days_left < 0):
                breach_msg = build_shelf_life_breach_message(item.name, days_in_stock, cat.default_shelf_life_days)
                alert = WasteAlert(
                    owner_id=user.id, item_id=item.id, item_name=item.name,
                    alert_type="shelf_life_breach", risk_score=risk,
                    days_to_expiry=days_left or 0, message=breach_msg,
                )
                db.add(alert)
                alerts.append(alert)

        if low_stock_enabled and 0 < item.quantity <= low_stock_threshold:
            low_msg = build_low_stock_message(item.name, item.quantity, low_stock_threshold, item.unit)
            alert = WasteAlert(
                owner_id=user.id, item_id=item.id, item_name=item.name,
                alert_type="low_stock", risk_score=risk,
                days_to_expiry=days_left or 0, message=low_msg,
            )
            db.add(alert)
            alerts.append(alert)

    db.commit()
    return [
        {
            "id": a.id, "item_id": a.item_id, "item_name": a.item_name,
            "alert_type": a.alert_type, "risk_score": a.risk_score,
            "days_to_expiry": a.days_to_expiry, "message": a.message,
            "is_resolved": a.is_resolved, "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Milestone 2 dashboard payload: KPIs, charts and the action center."""
    from routes.waste import ensure_tenant_data
    ensure_tenant_data(db, user.id)

    analytics = analytics_service.analytics(db, user.id, period="week")
    trend = analytics_service.trends(db, user.id, 30)
    fva = analytics_service.forecast_vs_actual_series(db, user.id, 30)

    items = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id).all()
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == user.id).all()}

    # action center data
    critical_items = []
    upcoming_expiries = []
    for item in items:
        cat = categories.get(item.category_id)
        days_left = days_to_expiry(item.expiry_date)
        risk = compute_risk_score(
            days_left, item.quantity,
            perishability_risk=cat.perishability_risk if cat else "medium",
            storage_requirement=cat.storage_requirement if cat else "ambient",
            waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
        )
        if risk >= 60:
            critical_items.append({
                "id": item.id, "name": item.name, "quantity": item.quantity,
                "risk_score": risk, "risk_level": risk_level(risk),
                "days_to_expiry": days_left,
            })
        status_val = expiration_status(days_left)
        if status_val in ("expiring_soon", "expired"):
            upcoming_expiries.append({
                "id": item.id, "name": item.name, "quantity": item.quantity,
                "days_to_expiry": days_left, "status": status_val,
            })
    critical_items.sort(key=lambda x: x["risk_score"], reverse=True)
    upcoming_expiries.sort(key=lambda x: (x["days_to_expiry"] if x["days_to_expiry"] is not None else 999))

    recommendations = (
        db.query(Recommendation)
        .filter(Recommendation.owner_id == user.id, Recommendation.status == "pending")
        .order_by(Recommendation.priority.asc())
        .limit(10)
        .all()
    )
    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.owner_id == user.id, Anomaly.is_resolved == False)  # noqa: E712
        .order_by(Anomaly.detected_at.desc())
        .limit(5)
        .all()
    )
    surplus = (
        db.query(SurplusAllocation)
        .filter(SurplusAllocation.owner_id == user.id, SurplusAllocation.status == "pending")
        .order_by(SurplusAllocation.urgency.asc())
        .limit(5)
        .all()
    )
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.owner_id == user.id, Notification.is_read == False)  # noqa: E712
        .scalar()
    ) or 0

    predicted_summary = analytics_service.predicted_waste(db, user.id, 7)

    return {
        "kpis": {
            **analytics["kpis"],
            "high_risk_items": analytics["kpis"]["high_risk_items"],
            "critical_items": analytics["kpis"]["critical_items"],
            "predicted_surplus": predicted_summary["total_surplus"],
            "unread_notifications": unread,
            "estimated_savings": _estimated_savings(analytics),
        },
        "risk_counts": analytics["risk_counts"],
        "waste_by_category": analytics["waste_by_category"],
        "top_waste_products": analytics["top_waste_products"],
        "waste_causes": analytics["waste_causes"],
        "forecast_accuracy": analytics["forecast_accuracy"],
        "trend": trend,
        "forecast_vs_actual": fva["series"],
        "action_center": {
            "critical_items": critical_items[:10],
            "recommendations": [
                {
                    "id": r.id, "item_id": r.item_id, "item_name": r.item_name,
                    "recommendation_type": r.recommendation_type,
                    "recommended_quantity": r.recommended_quantity,
                    "priority": r.priority, "reason": r.reason,
                    "expected_benefit": r.expected_benefit, "deadline": r.deadline,
                }
                for r in recommendations
            ],
            "recommended_donations": [
                {"item_id": r.item_id, "item_name": r.item_name, "quantity": r.recommended_quantity}
                for r in recommendations if r.recommendation_type == "donate_surplus"
            ][:5],
            "recommended_discounts": [
                {"item_id": r.item_id, "item_name": r.item_name, "quantity": r.recommended_quantity}
                for r in recommendations if r.recommendation_type == "discount"
            ][:5],
            "upcoming_expiries": upcoming_expiries[:10],
            "anomalies": [
                {
                    "id": a.id, "item_id": a.item_id, "item_name": a.item_name,
                    "anomaly_type": a.anomaly_type, "severity": a.severity,
                    "detected_value": a.detected_value, "expected_value": a.expected_value,
                    "explanation": a.explanation, "detected_at": a.detected_at,
                }
                for a in anomalies
            ],
            "surplus_allocations": [
                {
                    "id": s.id, "item_id": s.item_id, "item_name": s.item_name,
                    "surplus_quantity": s.surplus_quantity,
                    "safe_period_days": s.safe_period_days,
                    "urgency": s.urgency, "allocation_type": s.allocation_type,
                    "suggested_partner": s.suggested_partner,
                }
                for s in surplus
            ],
        },
    }


def _estimated_savings(analytics: dict) -> float:
    """Derived estimate: potential value recovered via donations + waste avoided."""
    donations_value = analytics["kpis"].get("donation_value", 0.0)
    predicted_value = analytics["kpis"].get("predicted_waste_value", 0.0)
    return round(donations_value + predicted_value * 0.25, 2)
