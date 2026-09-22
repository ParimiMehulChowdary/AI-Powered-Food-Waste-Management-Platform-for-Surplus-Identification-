from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.inventory_item import InventoryItem
from models.transaction import Transaction
from schemas.transaction import TransactionCreate, TransactionOut
from security import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

VALID_TYPES = {"purchase", "sale", "donation", "disposal", "adjustment"}


@router.get("", response_model=list[TransactionOut])
def list_transactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    txs = db.query(Transaction).filter(Transaction.owner_id == user.id).order_by(Transaction.transaction_date.desc()).all()
    return txs


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.transaction_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid transaction type. Allowed: {sorted(VALID_TYPES)}")

    item_name = None
    unit = "units"
    if payload.item_id:
        item = db.query(InventoryItem).filter(
            InventoryItem.id == payload.item_id, InventoryItem.owner_id == user.id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        item_name = item.name
        unit = item.unit

        if payload.transaction_type in ("sale", "donation", "disposal"):
            if payload.quantity > item.quantity:
                raise HTTPException(status_code=400, detail="Not enough stock")
            item.quantity -= payload.quantity

    tx = Transaction(
        owner_id=user.id, item_id=payload.item_id, item_name=item_name,
        transaction_type=payload.transaction_type, quantity=payload.quantity,
        unit=unit, unit_price=payload.unit_price, reference=payload.reference,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
