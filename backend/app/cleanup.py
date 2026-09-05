"""File cleanup cron — removes expired jobs and old files."""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings
from .database import SessionLocal
from . import models


def cleanup_old_files(days: int = 30):
    """Delete jobs older than N days and their files."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    db = SessionLocal()
    deleted = 0

    try:
        old_jobs = db.query(models.Job).filter(
            models.Job.created_at < cutoff
        ).all()

        for job in old_jobs:
            # Delete files from disk
            job_dir = Path(settings.DATA_DIR) / "files" / job.uuid
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)

            # Delete from DB (cascade handles ShareLink etc)
            db.delete(job)
            deleted += 1

        db.commit()
    finally:
        db.close()

    return deleted


def cleanup_expired_shares():
    """Deactivate expired share links."""
    db = SessionLocal()
    deactivated = 0

    try:
        expired = db.query(models.ShareLink).filter(
            models.ShareLink.is_active == True,  # noqa
            models.ShareLink.expires_at < datetime.utcnow()
        ).all()

        for share in expired:
            share.is_active = False
            deactivated += 1

        db.commit()
    finally:
        db.close()

    return deactivated
