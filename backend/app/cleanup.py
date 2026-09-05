"""File cleanup cron — removes expired jobs and old files."""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings
from .database import SessionLocal
from . import models


def cleanup_old_files(days: int = 30):
    """Delete jobs older than their owner's retention period.
    Free users: 30 days default (+7 per ad click, max 180).
    keep_files_forever users: skipped entirely."""
    db = SessionLocal()
    deleted = 0

    try:
        all_jobs = db.query(models.Job).all()

        for job in all_jobs:
            # Check owner's retention
            if job.user_id:
                owner = db.query(models.User).filter(
                    models.User.id == job.user_id
                ).first()
                if owner and getattr(owner, "keep_files_forever", False):
                    continue
                retention = getattr(owner, "retention_days", 30) or 30
            else:
                retention = 7  # anon files: 7 days
            cutoff = datetime.utcnow() - timedelta(days=retention)
            if job.created_at > cutoff:
                continue
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
