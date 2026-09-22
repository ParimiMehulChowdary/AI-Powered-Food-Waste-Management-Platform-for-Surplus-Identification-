"""Notification generation with duplicate suppression.

Notifications carry severity, message, product and read/unread state. A
dedupe key (owner + type + item + event date) prevents re-sending the same
event, matching the scheduler's daily cadence.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from models.notification import Notification


def _key(owner_id: int, ntype: str, item_id: int | None, event_date: str) -> str:
    raw = f"{owner_id}:{ntype}:{item_id or 0}:{event_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def notify(
    db: Session,
    owner_id: int,
    notification_type: str,
    severity: str,
    message: str,
    item_id: int | None = None,
    item_name: str | None = None,
    source_ref: str | None = None,
    event_date: str | None = None,
) -> Notification | None:
    """Create a notification unless an identical one already exists."""
    event_date = event_date or datetime.utcnow().strftime("%Y-%m-%d")
    key = _key(owner_id, notification_type, item_id, event_date)
    exists = db.query(Notification).filter(Notification.dedupe_key == key).first()
    if exists:
        return None
    notification = Notification(
        owner_id=owner_id,
        item_id=item_id,
        item_name=item_name,
        notification_type=notification_type,
        severity=severity,
        message=message,
        source_ref=source_ref,
        dedupe_key=key,
    )
    db.add(notification)
    db.flush()
    return notification


def today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")