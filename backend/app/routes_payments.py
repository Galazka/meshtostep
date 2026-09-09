"""Stripe webhook placeholder — credit system removed. — 3dfile.link"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db

router = APIRouter(prefix="/api", tags=["payments"])


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook — currently a no-op placeholder."""
    return {"ok": True}
