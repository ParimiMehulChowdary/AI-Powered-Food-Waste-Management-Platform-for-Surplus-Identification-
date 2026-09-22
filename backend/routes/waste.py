from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.waste_prediction import WastePrediction
from models.risk_assessment import RiskAssessment
from models.recommendation import Recommendation
from models.anomaly import Anomaly
from models.waste_cause import WasteCause
from models.inventory_item import InventoryItem
from models.category import Category

from security import get_current_user
from services import analytics_service, forecast_evaluator, inventory_optimization
from services.forecasting import forecast_item, generate_predictions_for_item
from schemas.waste_prediction import WastePredictionOut
from schemas.risk_assessment import RiskAssessmentOut
from schemas.anomaly import AnomalyOut

router = APIRouter(prefix="/api/waste", tags=["waste"])


def ensure_tenant_data(db: Session, owner_id: int, force: bool = False) -> bool:
    """Run the daily inference job once for a tenant with no data yet."""
    has_data = (
        db.query(WastePrediction).filter(WastePrediction.owner_id == owner_id).count()
        or db.query(RiskAssessment).filter(RiskAssessment.owner_id == owner_id).count()
        or db.query(Recommendation).filter(Recommendation.owner_id == owner_id).count()
    )
    if not force and has_data:
        return False
    from jobs.daily import run_for_tenant
    run_for_tenant(db, owner_id)
    return True


@router.post("/jobs/daily")
def run_daily_job(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Trigger the daily AI job for the current business (predictions, risk,
    anomalies, recommendations, surplus, notifications)."""
    from jobs.daily import run_for_tenant
    try:
        summary = run_for_tenant(db, user.id)
        return {"status": "ok", "type": "daily", "summary": summary}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Daily job failed: {exc}")


@router.post("/predict")
def predict_on_demand(
    item_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate demand/waste/surplus predictions now (inference only)."""
    items = db.query(InventoryItem).filter(
        InventoryItem.owner_id == user.id,
        InventoryItem.id == item_id if item_id else InventoryItem.owner_id == user.id,
    ).all()
    seen = set()
    summaries = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        _rows, summary = generate_predictions_for_item(db, item, user.id, horizon_days=7)
        summaries.append({
            "item_id": item.id,
            "item_name": item.name,
            "model_name": summary["model_name"],
            "is_fallback": summary["is_fallback"],
            "confidence": summary["confidence"],
            "total_demand": summary["total_demand"],
            "total_waste": summary["total_waste"],
            "total_surplus": summary["total_surplus"],
        })
    db.commit()
    return {"status": "ok", "predictions_generated": len(summaries), "items": summaries}


@router.get("/predictions", response_model=list[WastePredictionOut])
def list_predictions(
    item_id: int | None = Query(None, description="Filter to a single product"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_tenant_data(db, user.id)
    q = db.query(WastePrediction).filter(WastePrediction.owner_id == user.id)
    if item_id:
        q = q.filter(WastePrediction.item_id == item_id)
    rows = q.order_by(WastePrediction.target_date.desc()).offset(offset).limit(limit).all()
    return rows


@router.get("/predictions/summary")
def predictions_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Latest forecast per product."""
    ensure_tenant_data(db, user.id)
    preds = db.query(WastePrediction).filter(WastePrediction.owner_id == user.id).all()
    latest_by_item: dict[int, WastePrediction] = {}
    for p in preds:
        cur = latest_by_item.get(p.item_id)
        if cur is None or p.target_date > cur.target_date:
            latest_by_item[p.item_id] = p
    return [
        {
            "item_id": p.item_id,
            "item_name": p.item_name,
            "predicted_demand": p.predicted_demand,
            "predicted_waste": p.predicted_waste,
            "predicted_surplus": p.predicted_surplus,
            "waste_probability": p.waste_probability,
            "waste_risk_level": p.waste_risk_level,
            "expected_waste_value": p.expected_waste_value,
            "confidence": p.confidence,
            "model_name": p.model_name,
            "is_fallback": p.is_fallback,
            "target_date": p.target_date,
        }
        for p in sorted(latest_by_item.values(), key=lambda x: x.item_name or "")
    ]


@router.get("/risk", response_model=list[RiskAssessmentOut])
def list_risk(
    risk_level: str | None = Query(None, pattern="^(low|moderate|high|critical)$"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_tenant_data(db, user.id)
    q = db.query(RiskAssessment).filter(RiskAssessment.owner_id == user.id)
    if risk_level:
        q = q.filter(RiskAssessment.risk_level == risk_level)
    rows = q.order_by(RiskAssessment.risk_score.desc()).offset(offset).limit(limit).all()
    return rows


@router.get("/analytics")
def analytics(
    period: str = Query("week", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return analytics_service.analytics(db, user.id, period)


@router.get("/trends")
def trends(
    days: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {
        "daily": analytics_service.trends(db, user.id, days),
        "forecast_vs_actual": analytics_service.forecast_vs_actual_series(db, user.id, days),
    }


@router.get("/causes")
def list_causes(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_tenant_data(db, user.id)
    rows = db.query(WasteCause).filter(WasteCause.owner_id == user.id).order_by(WasteCause.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": c.id, "item_id": c.item_id, "item_name": c.item_name,
            "cause": c.cause, "explanation": c.explanation, "confidence": c.confidence,
            "period_start": c.period_start, "period_end": c.period_end, "created_at": c.created_at,
        }
        for c in rows
    ]


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    include_resolved: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_tenant_data(db, user.id)
    q = db.query(Anomaly).filter(Anomaly.owner_id == user.id)
    if not include_resolved:
        q = q.filter(Anomaly.is_resolved == False)  # noqa: E712
    rows = q.order_by(Anomaly.detected_at.desc()).offset(offset).limit(limit).all()
    return rows


@router.post("/anomalies/{anomaly_id}/resolve")
def resolve_anomaly(anomaly_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id, Anomaly.owner_id == user.id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    anomaly.is_resolved = True
    db.commit()
    return {"detail": "Anomaly resolved"}


@router.get("/forecast-accuracy")
def forecast_accuracy(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return forecast_evaluator.tenant_headline(db, user.id)


@router.get("/reorder")
def reorder_recommendations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Inventory optimization: recommended order quantities per product."""
    ensure_tenant_data(db, user.id)
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id).all()
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == user.id).all()}
    predictions = db.query(WastePrediction).filter(WastePrediction.owner_id == user.id).all()
    by_item: dict[int, list[WastePrediction]] = {}
    for p in predictions:
        by_item.setdefault(p.item_id, []).append(p)

    from services.risk_service import days_to_expiry

    out = []
    for item in items:
        cat = categories.get(item.category_id)
        stored = by_item.get(item.id)
        if stored:
            total_demand = sum(p.predicted_demand for p in stored)
            pred = max(stored, key=lambda p: p.target_date)
            forecast = {
                "total_demand": total_demand,
                "horizon_days": 7,
                "days_to_expiry": days_to_expiry(item.expiry_date) if item.expiry_date else None,
                "cost_per_unit": item.cost_per_unit,
            }
        else:
            try:
                forecast = forecast_item(db, item, horizon_days=7)
            except Exception:  # noqa: BLE001
                continue
        reorder = inventory_optimization.optimize_item(item, forecast, cat)
        out.append(reorder)

    out.sort(key=lambda r: (r["recommended_quantity"] > 0, -r["recommended_quantity"]), reverse=False)
    return out