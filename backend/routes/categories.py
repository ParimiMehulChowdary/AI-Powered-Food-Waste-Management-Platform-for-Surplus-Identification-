from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.user import User
from models.category import Category
from models.inventory_item import InventoryItem
from schemas.category import CategoryCreate, CategoryUpdate, CategoryOut
from security import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    {"name": "Dairy & Eggs", "description": "Milk, cheese, yogurt, butter, eggs", "perishability_risk": "high", "storage_requirement": "chilled", "default_shelf_life_days": 7, "waste_risk_weight": 1.4},
    {"name": "Fresh Produce", "description": "Fruits, vegetables, herbs, salads", "perishability_risk": "high", "storage_requirement": "chilled", "default_shelf_life_days": 5, "waste_risk_weight": 1.5},
    {"name": "Meat & Poultry", "description": "Beef, chicken, pork, lamb, deli meats", "perishability_risk": "high", "storage_requirement": "chilled", "default_shelf_life_days": 4, "waste_risk_weight": 1.5},
    {"name": "Seafood", "description": "Fish, shrimp, shellfish", "perishability_risk": "high", "storage_requirement": "chilled", "default_shelf_life_days": 3, "waste_risk_weight": 1.5},
    {"name": "Bakery & Bread", "description": "Bread, pastries, cakes, tortillas", "perishability_risk": "medium", "storage_requirement": "ambient", "default_shelf_life_days": 5, "waste_risk_weight": 1.2},
    {"name": "Beverages", "description": "Juice, soft drinks, water, coffee", "perishability_risk": "low", "storage_requirement": "ambient", "default_shelf_life_days": 30, "waste_risk_weight": 0.5},
    {"name": "Frozen Foods", "description": "Frozen meals, ice cream, frozen vegetables", "perishability_risk": "low", "storage_requirement": "frozen", "default_shelf_life_days": 90, "waste_risk_weight": 0.4},
    {"name": "Canned & Jarred", "description": "Canned goods, jarred sauces, pickles", "perishability_risk": "low", "storage_requirement": "ambient", "default_shelf_life_days": 365, "waste_risk_weight": 0.3},
    {"name": "Dry Goods & Grains", "description": "Rice, pasta, cereal, flour, oats", "perishability_risk": "low", "storage_requirement": "ambient", "default_shelf_life_days": 180, "waste_risk_weight": 0.3},
    {"name": "Condiments & Sauces", "description": "Ketchup, mustard, soy sauce, oils", "perishability_risk": "low", "storage_requirement": "ambient", "default_shelf_life_days": 90, "waste_risk_weight": 0.4},
    {"name": "Snacks", "description": "Chips, nuts, crackers, cookies", "perishability_risk": "low", "storage_requirement": "ambient", "default_shelf_life_days": 60, "waste_risk_weight": 0.4},
    {"name": "Deli & Prepared", "description": "Ready-to-eat meals, sandwiches, salads", "perishability_risk": "high", "storage_requirement": "chilled", "default_shelf_life_days": 3, "waste_risk_weight": 1.5},
]


def _to_out(cat: Category, db: Session) -> CategoryOut:
    count = db.query(func.count(InventoryItem.id)).filter(
        InventoryItem.category_id == cat.id,
        InventoryItem.owner_id == cat.owner_id,
    ).scalar() or 0
    out = CategoryOut.model_validate(cat)
    out.item_count = count
    return out


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cats = db.query(Category).filter(Category.owner_id == user.id).all()
    return [_to_out(c, db) for c in cats]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = Category(owner_id=user.id, **payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _to_out(cat, db)


@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, payload: CategoryUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = db.query(Category).filter(Category.id == cat_id, Category.owner_id == user.id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return _to_out(cat, db)


@router.delete("/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(cat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = db.query(Category).filter(Category.id == cat_id, Category.owner_id == user.id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.query(InventoryItem).filter(InventoryItem.category_id == cat.id).update({"category_id": None})
    db.delete(cat)
    db.commit()


@router.post("/seed", response_model=list[CategoryOut])
def seed_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing_names = {
        c.name.strip().lower()
        for c in db.query(Category).filter(Category.owner_id == user.id).all()
    }
    created = []
    for cat_data in DEFAULT_CATEGORIES:
        if cat_data["name"].strip().lower() in existing_names:
            continue
        cat = Category(owner_id=user.id, **cat_data)
        db.add(cat)
        db.flush()
        created.append(_to_out(cat, db))
    db.commit()
    all_cats = db.query(Category).filter(Category.owner_id == user.id).order_by(Category.id).all()
    return [_to_out(c, db) for c in all_cats]
