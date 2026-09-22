from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.surplus_allocation import SurplusAllocation
from models.donation_partner import DonationPartner
from security import get_current_user
from schemas.surplus import SurplusAllocationOut, SurplusStatusUpdate, DonationPartnerCreate, DonationPartnerOut

router = APIRouter(prefix="/api/surplus", tags=["surplus"])

VALID_STATUS = {"pending", "actioned", "dismissed"}


@router.get("/allocations", response_model=list[SurplusAllocationOut])
def list_allocations(
    status: str | None = Query(None, pattern="^(pending|actioned|dismissed)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.waste import ensure_tenant_data
    ensure_tenant_data(db, user.id)
    q = db.query(SurplusAllocation).filter(SurplusAllocation.owner_id == user.id)
    if status:
        q = q.filter(SurplusAllocation.status == status)
    return q.order_by(SurplusAllocation.urgency.asc()).offset(offset).limit(limit).all()


@router.patch("/allocations/{allocation_id}", response_model=SurplusAllocationOut)
def update_allocation_status(
    allocation_id: int,
    payload: SurplusStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(VALID_STATUS)}")
    allocation = db.query(SurplusAllocation).filter(
        SurplusAllocation.id == allocation_id, SurplusAllocation.owner_id == user.id
    ).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    allocation.status = payload.status
    db.commit()
    db.refresh(allocation)
    return allocation


@router.get("/partners", response_model=list[DonationPartnerOut])
def list_partners(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(DonationPartner).filter(DonationPartner.owner_id == user.id).order_by(DonationPartner.name.asc()).all()


@router.post("/partners", response_model=DonationPartnerOut, status_code=201)
def create_partner(payload: DonationPartnerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    partner = DonationPartner(owner_id=user.id, **payload.model_dump())
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner