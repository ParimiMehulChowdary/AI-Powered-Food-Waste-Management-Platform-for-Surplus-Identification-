from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import secrets

from database import get_db
from models.user import User
from models.business_settings import BusinessSettings
from models.api_key import ApiKey
from schemas.business_settings import BusinessSettingsUpdate, BusinessSettingsOut
from schemas.api_key import ApiKeyCreate, ApiKeyOut
from security import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=BusinessSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings = db.query(BusinessSettings).filter(BusinessSettings.owner_id == user.id).first()
    if not settings:
        settings = BusinessSettings(owner_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.put("", response_model=BusinessSettingsOut)
def update_settings(payload: BusinessSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings = db.query(BusinessSettings).filter(BusinessSettings.owner_id == user.id).first()
    if not settings:
        settings = BusinessSettings(owner_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    keys = db.query(ApiKey).filter(ApiKey.owner_id == user.id).all()
    out = []
    for k in keys:
        item = ApiKeyOut.model_validate(k)
        if item.key and len(item.key) > 8:
            item.key = f"{item.key[:4]}...{item.key[-4:]}"
        out.append(item)
    return out


@router.post("/api-keys", response_model=ApiKeyOut, status_code=201)
def create_api_key(payload: ApiKeyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    key = ApiKey(owner_id=user.id, label=payload.label, key=f"fw_{secrets.token_urlsafe(32)}")
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyOut.model_validate(key)


@router.delete("/api-keys/{key_id}", status_code=204)
def delete_api_key(key_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.owner_id == user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
