from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv
import io

from database import get_db
from models.user import User
from models.category import Category
from models.inventory_item import InventoryItem
from models.transaction import Transaction
from schemas.inventory_item import InventoryItemCreate, InventoryItemUpdate, InventoryItemOut
from security import get_current_user
from services.risk_service import (
    compute_risk_score, days_to_expiry, risk_level,
    expiration_status,
)
from services.csv_service import parse_csv_content

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _to_out(item: InventoryItem, db: Session) -> InventoryItemOut:
    cat = db.query(Category).filter(Category.id == item.category_id).first() if item.category_id else None
    days_left = days_to_expiry(item.expiry_date)
    risk = compute_risk_score(
        days_left,
        item.quantity,
        perishability_risk=cat.perishability_risk if cat else "medium",
        storage_requirement=cat.storage_requirement if cat else "ambient",
        waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
    )
    out = InventoryItemOut.model_validate(item)
    out.category_name = cat.name if cat else None
    out.perishability_risk = cat.perishability_risk if cat else None
    out.days_to_expiry = days_left
    out.risk_score = risk
    out.risk_level = risk_level(risk)
    return out


@router.get("", response_model=list[InventoryItemOut])
def list_items(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    category_id: int | None = Query(None),
    risk_level_filter: str | None = Query(None, alias="risk_level"),
    expiry_status: str | None = Query(None),
    search: str | None = Query(None),
):
    query = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id)

    if category_id is not None:
        query = query.filter(InventoryItem.category_id == category_id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            InventoryItem.name.ilike(like)
            | InventoryItem.sku.ilike(like)
            | InventoryItem.barcode.ilike(like)
            | InventoryItem.supplier.ilike(like)
        )

    items = query.all()

    if expiry_status or risk_level_filter:
        categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == user.id).all()}
        filtered = []
        for item in items:
            cat = categories.get(item.category_id)
            days_left = days_to_expiry(item.expiry_date)
            status_val = expiration_status(days_left)
            risk = compute_risk_score(
                days_left, item.quantity,
                perishability_risk=cat.perishability_risk if cat else "medium",
                storage_requirement=cat.storage_requirement if cat else "ambient",
                waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
            )
            if expiry_status and status_val != expiry_status:
                continue
            if risk_level_filter and risk_level(risk) != risk_level_filter:
                continue
            filtered.append(item)
        items = filtered

    return [_to_out(i, db) for i in items]


@router.get("/barcode/{barcode}", response_model=InventoryItemOut)
def get_item_by_barcode(barcode: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(
        InventoryItem.owner_id == user.id,
        InventoryItem.barcode == barcode,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="No item found with that barcode")
    return _to_out(item, db)


@router.get("/{item_id}", response_model=InventoryItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return _to_out(item, db)


@router.post("", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: InventoryItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = InventoryItem(owner_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    if payload.quantity:
        db.add(Transaction(
            owner_id=user.id, item_id=item.id, item_name=item.name,
            transaction_type="purchase", quantity=payload.quantity,
            unit=item.unit, reference="Initial stock",
        ))
        db.commit()
    return _to_out(item, db)


@router.put("/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: int, payload: InventoryItemUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _to_out(item, db)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()


@router.post("/sale/{item_id}", response_model=InventoryItemOut)
def record_sale(item_id: int, quantity: float = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if quantity > item.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    item.quantity -= quantity
    db.add(Transaction(
        owner_id=user.id, item_id=item.id, item_name=item.name,
        transaction_type="sale", quantity=quantity, unit=item.unit,
        unit_price=item.cost_per_unit, reference="Recorded sale",
    ))
    db.commit()
    db.refresh(item)
    return _to_out(item, db)


@router.post("/donate/{item_id}", response_model=InventoryItemOut)
def record_donation(item_id: int, quantity: float = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if quantity > item.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    item.quantity -= quantity
    item.is_surplus_listed = False
    db.add(Transaction(
        owner_id=user.id, item_id=item.id, item_name=item.name,
        transaction_type="donation", quantity=quantity, unit=item.unit,
        reference="Redistribution donation",
    ))
    db.commit()
    db.refresh(item)
    return _to_out(item, db)


@router.post("/dispose/{item_id}", response_model=InventoryItemOut)
def record_disposal(item_id: int, quantity: float = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if quantity > item.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    item.quantity -= quantity
    db.add(Transaction(
        owner_id=user.id, item_id=item.id, item_name=item.name,
        transaction_type="disposal", quantity=quantity, unit=item.unit,
        reference="Waste disposal",
    ))
    db.commit()
    db.refresh(item)
    return _to_out(item, db)


@router.post("/bulk", response_model=dict)
async def bulk_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        parsed = parse_csv_content(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    created = 0
    for row in parsed["items"]:
        item = InventoryItem(owner_id=user.id, **row)
        db.add(item)
        db.flush()
        created += 1
        if row.get("quantity"):
            db.add(Transaction(
                owner_id=user.id, item_id=item.id, item_name=item.name,
                transaction_type="purchase", quantity=row["quantity"],
                unit=item.unit, reference="CSV bulk upload",
            ))
    db.commit()
    return {"created": created, "errors": parsed["errors"]}


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == user.id).all()
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == user.id).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "sku", "barcode", "category", "quantity", "unit",
        "cost_per_unit", "expiry_date", "days_to_expiry", "storage_location",
        "supplier", "risk_score", "risk_level", "created_at",
    ])

    for item in items:
        cat = categories.get(item.category_id)
        days_left = days_to_expiry(item.expiry_date)
        risk = compute_risk_score(
            days_left, item.quantity,
            perishability_risk=cat.perishability_risk if cat else "medium",
            storage_requirement=cat.storage_requirement if cat else "ambient",
            waste_risk_weight=cat.waste_risk_weight if cat else 1.0,
        )
        writer.writerow([
            item.id, item.name, item.sku or "", item.barcode or "",
            cat.name if cat else "Uncategorized", item.quantity, item.unit,
            item.cost_per_unit,
            item.expiry_date.strftime("%Y-%m-%d") if item.expiry_date else "",
            days_left if days_left is not None else "",
            item.storage_location or "", item.supplier or "",
            round(risk, 1), risk_level(risk),
            item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_export.csv"},
    )
