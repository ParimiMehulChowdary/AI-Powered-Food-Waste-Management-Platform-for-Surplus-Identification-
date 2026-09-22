from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.notification import Notification
from security import get_current_user
from schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.query(Notification).filter(
        Notification.owner_id == user.id, Notification.is_read == False  # noqa: E712
    ).count()
    return {"count": count}


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    notification_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.owner_id == user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    if notification_type:
        q = q.filter(Notification.notification_type == notification_type)
    return q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.query(Notification).filter(
        Notification.id == notification_id, Notification.owner_id == user.id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"detail": "Notification marked as read"}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    updated = db.query(Notification).filter(
        Notification.owner_id == user.id, Notification.is_read == False  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"detail": "All notifications marked as read", "updated": updated}