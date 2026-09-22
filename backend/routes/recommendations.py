from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.recommendation import Recommendation
from security import get_current_user
from schemas.recommendation import RecommendationOut, RecommendationStatusUpdate

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

VALID_STATUS = {"pending", "applied", "rejected", "expired"}


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(
    status: str | None = Query(None, pattern="^(pending|applied|rejected|expired)$"),
    include_archived: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.waste import ensure_tenant_data
    ensure_tenant_data(db, user.id)
    q = db.query(Recommendation).filter(Recommendation.owner_id == user.id)
    if status:
        q = q.filter(Recommendation.status == status)
    elif not include_archived:
        q = q.filter(Recommendation.status == "pending")
    rows = q.order_by(Recommendation.priority.asc(), Recommendation.created_at.desc()).offset(offset).limit(limit).all()
    return rows


@router.patch("/{rec_id}", response_model=RecommendationOut)
def update_recommendation_status(
    rec_id: int,
    payload: RecommendationStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(VALID_STATUS)}")
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id, Recommendation.owner_id == user.id
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.status = payload.status
    db.commit()
    db.refresh(rec)
    return rec