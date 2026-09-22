from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models.user import User
from models.api_key import ApiKey
from models.category import Category
from models.inventory_item import InventoryItem
from models.transaction import Transaction
from services.risk_service import days_to_expiry, compute_risk_score, risk_level
from services.csv_service import parse_expiry, parse_float

router = APIRouter(prefix="/api/pos", tags=["pos-integration"])


def get_user_from_api_key(x_api_key: str = Header(...), db: Session = Depends(get_db)) -> User:
    api_key = db.query(ApiKey).filter(ApiKey.key == x_api_key, ApiKey.is_active == True).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    user = db.query(User).filter(User.id == api_key.owner_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="API key owner not found")
    return user


@router.post("/inventory")
def pos_inventory_push(
    items: list[dict],
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """Accept POS-formatted inventory data and create/update items.
    Each item dict should contain: name, quantity, barcode (optional), sku (optional),
    expiry_date (optional, YYYY-MM-DD), category_id (optional).
    """
    created = 0
    updated = 0
    errors = []

    for idx, item_data in enumerate(items, start=1):
        name = item_data.get("name", "").strip()
        if not name:
            errors.append(f"Item {idx}: missing required 'name'")
            continue

        barcode = item_data.get("barcode")
        sku = item_data.get("sku")

        existing = None
        if barcode:
            existing = db.query(InventoryItem).filter(
                InventoryItem.owner_id == user.id,
                InventoryItem.barcode == barcode,
            ).first()
        if not existing and sku:
            existing = db.query(InventoryItem).filter(
                InventoryItem.owner_id == user.id,
                InventoryItem.sku == sku,
            ).first()

        quantity = parse_float(item_data.get("quantity"), 0.0)
        expiry = parse_expiry(item_data.get("expiry_date"))
        category_id = item_data.get("category_id")

        if existing:
            existing.quantity = quantity
            if expiry:
                existing.expiry_date = expiry
            if item_data.get("unit"):
                existing.unit = item_data["unit"]
            if item_data.get("cost_per_unit") is not None:
                existing.cost_per_unit = parse_float(item_data.get("cost_per_unit"), 0.0)
            if category_id:
                existing.category_id = int(category_id)
            if item_data.get("storage_location"):
                existing.storage_location = item_data["storage_location"]
            updated += 1
        else:
            new_item = InventoryItem(
                owner_id=user.id,
                name=name,
                category_id=int(category_id) if category_id else None,
                sku=sku,
                barcode=barcode,
                quantity=quantity,
                unit=item_data.get("unit", "units"),
                cost_per_unit=parse_float(item_data.get("cost_per_unit"), 0.0),
                expiry_date=expiry,
                storage_location=item_data.get("storage_location"),
                supplier=item_data.get("supplier"),
            )
            db.add(new_item)
            db.flush()
            if quantity > 0:
                db.add(Transaction(
                    owner_id=user.id, item_id=new_item.id, item_name=new_item.name,
                    transaction_type="purchase", quantity=quantity,
                    unit=new_item.unit, reference="POS inventory push",
                ))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


@router.post("/sales")
def pos_record_sale(
    sale: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """Record a sale from POS. Requires: barcode or sku, quantity.
    Optional: unit_price, reference."""
    barcode = sale.get("barcode")
    sku = sale.get("sku")
    quantity = parse_float(sale.get("quantity"), 0.0)

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    item = None
    if barcode:
        item = db.query(InventoryItem).filter(
            InventoryItem.owner_id == user.id,
            InventoryItem.barcode == barcode,
        ).first()
    if not item and sku:
        item = db.query(InventoryItem).filter(
            InventoryItem.owner_id == user.id,
            InventoryItem.sku == sku,
        ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found by barcode or SKU")

    if quantity > item.quantity:
        raise HTTPException(status_code=400, detail=f"Not enough stock. Available: {item.quantity}")

    item.quantity -= quantity
    db.add(Transaction(
        owner_id=user.id, item_id=item.id, item_name=item.name,
        transaction_type="sale", quantity=quantity, unit=item.unit,
        unit_price=sale.get("unit_price", item.cost_per_unit),
        reference=sale.get("reference", "POS sale"),
    ))
    db.commit()
    db.refresh(item)

    return {
        "id": item.id, "name": item.name,
        "remaining_quantity": item.quantity, "unit": item.unit,
    }


@router.post("/webhook/inventory-update")
def pos_webhook_inventory_update(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """Webhook-style endpoint for real-time POS inventory sync.
    Expects a single item update: {barcode, quantity, expiry_date?}.
    """
    barcode = payload.get("barcode")
    if not barcode:
        raise HTTPException(status_code=400, detail="barcode is required")

    item = db.query(InventoryItem).filter(
        InventoryItem.owner_id == user.id,
        InventoryItem.barcode == barcode,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found by barcode")

    quantity = payload.get("quantity")
    if quantity is not None:
        item.quantity = parse_float(quantity, item.quantity)

    expiry = payload.get("expiry_date")
    if expiry:
        parsed = parse_expiry(expiry)
        if parsed:
            item.expiry_date = parsed

    if payload.get("storage_location"):
        item.storage_location = payload["storage_location"]

    db.commit()
    db.refresh(item)

    days_left = days_to_expiry(item.expiry_date)
    cat = db.query(Category).filter(Category.id == item.category_id).first() if item.category_id else None
    risk = compute_risk_score(
        days_left, item.quantity,
        perishability_risk=cat.perishability_risk if cat else "medium",
        storage_requirement=cat.storage_requirement if cat else "ambient",
        waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
    )

    return {
        "id": item.id, "name": item.name,
        "quantity": item.quantity, "unit": item.unit,
        "days_to_expiry": days_left,
        "risk_score": risk, "risk_level": risk_level(risk),
    }
