"""Standalone scheduler for Milestone 2 AI jobs.

Pure-python loop with zero extra dependencies. Run as a separate process so it
does not interfere with ``uvicorn --reload``.

Usage:
    python scheduler.py            # long-running loop (daily + weekly jobs)
    python scheduler.py --once     # run all due jobs once, then exit
    python scheduler.py --daily    # run the daily job now and exit
    python scheduler.py --weekly   # run the weekly job now and exit

Schedule is controlled via backend/.env:
    DAILY_JOB_TIME    (HH:MM, default 02:00)
    WEEKLY_JOB_DAY    (mon..sun, default mon)
    WEEKLY_JOB_TIME   (HH:MM, default 03:00)
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta

from database import SessionLocal
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scheduler")

WEEKDAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_hhmm(value: str, fallback: str) -> str:
    try:
        hh, mm = value.split(":")
        assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
        return f"{int(hh):02d}:{int(mm):02d}"
    except (ValueError, AssertionError):
        return fallback


def next_at(hhmm: str) -> datetime:
    now = datetime.now()
    hh, mm = hhmm.split(":")
    candidate = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_weekly(day: int, hhmm: str) -> datetime:
    now = datetime.now()
    hh, mm = hhmm.split(":")
    candidate = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    while candidate.weekday() != day or candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def run_daily_job() -> None:
    from jobs.daily import run_daily
    db = SessionLocal()
    try:
        result = run_daily(db)
        logger.info("Daily job complete: %s", result)
    finally:
        db.close()


def run_weekly_job() -> None:
    from jobs.weekly import run_weekly
    db = SessionLocal()
    try:
        result = run_weekly(db)
        logger.info("Weekly job complete: %s", result)
    finally:
        db.close()


def loop() -> None:
    daily_time = _parse_hhmm(settings.DAILY_JOB_TIME, "02:00")
    day_raw = settings.WEEKLY_JOB_DAY.lower().strip()
    weekly_day = WEEKDAY_INDEX.get(day_raw, 0)
    weekly_time = _parse_hhmm(settings.WEEKLY_JOB_TIME, "03:00")

    next_daily = next_at(daily_time)
    next_weekly = next_weekly(weekly_day, weekly_time)
    logger.info("Scheduler started. daily=%s weekly=%s (%s), checks every 60s", next_daily.isoformat(), next_weekly.isoformat(), day_raw)

    while True:
        now = datetime.now()
        if now >= next_daily:
            run_daily_job()
            next_daily = next_at(daily_time)
        if now >= next_weekly:
            run_weekly_job()
            next_weekly = next_weekly(weekly_day, weekly_time)
        time.sleep(60)


def main() -> None:
    args = sys.argv[1:]
    if "--daily" in args:
        run_daily_job()
        return
    if "--weekly" in args:
        run_weekly_job()
        return
    if "--once" in args:
        now = datetime.now()
        run_daily_job()
        run_weekly_job()
        logger.info("One-off run complete in %.1fs", (datetime.now() - now).total_seconds())
        return
    loop()


if __name__ == "__main__":
    main()