from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.simulation import Simulation
from models.inventory_item import InventoryItem
from security import get_current_user
from services.simulation_engine import run_simulation
from schemas.simulation import SimulationOut

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


class SimulationRequest(BaseModel):
    item_id: int | None = None
    current_stock: float | None = None
    purchase_quantity: float = 0.0
    discount_pct: float = 0.0
    expected_demand: float | None = None
    donation_quantity: float = 0.0
    horizon_days: int = 7
    elasticity: float = 0.5
    save: bool = True


@router.post("")
def run_simulation_endpoint(payload: SimulationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = None
    if payload.item_id is not None:
        item = db.query(InventoryItem).filter(
            InventoryItem.id == payload.item_id, InventoryItem.owner_id == user.id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

    params = {
        "current_stock": payload.current_stock,
        "purchase_quantity": payload.purchase_quantity,
        "discount_pct": payload.discount_pct,
        "expected_demand": payload.expected_demand,
        "donation_quantity": payload.donation_quantity,
        "horizon_days": payload.horizon_days,
        "elasticity": payload.elasticity,
        "item_name": item.name if item else None,
    }
    try:
        result = run_simulation(item, forecast=None, params=params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if payload.save and item is not None:
        simulation = Simulation(
            owner_id=user.id,
            user_id=user.id,
            item_id=item.id,
            item_name=item.name,
            input_parameters={k: v for k, v in params.items() if v is not None},
            results=result,
        )
        db.add(simulation)
        db.commit()
        db.refresh(simulation)
        result["id"] = simulation.id
    elif payload.save:
        simulation = Simulation(
            owner_id=user.id,
            user_id=user.id,
            item_id=None,
            item_name=params.get("item_name"),
            input_parameters={k: v for k, v in params.items() if v is not None},
            results=result,
        )
        db.add(simulation)
        db.commit()
        result["id"] = simulation.id

    return result


@router.get("", response_model=list[SimulationOut])
def list_simulations(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Simulation)
        .filter(Simulation.owner_id == user.id)
        .order_by(Simulation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows