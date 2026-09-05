"""Delete job + its files (admin only)."""
import os
import shutil
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Job
from . import require_admin


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    # Delete files from disk
    from ..config import settings
    jobs_dir = os.path.join(settings.DATA_DIR, "jobs")
    job_dir = os.path.join(jobs_dir, job.uuid)
    if os.path.isdir(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)

    db.delete(job)
    db.commit()
    return {"ok": True}
