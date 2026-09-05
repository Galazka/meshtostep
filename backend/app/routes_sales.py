"""Paid models — 20% commission — 3dhosty.com"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from . import models
from .auth import get_current_user
from .config import settings

router = APIRouter(prefix="/api/models", tags=["sales"])

@router.post("/{job_id}/purchase")
def purchase(job_id: int, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id==job_id, models.Job.status=="done").first()
    if not job:
        raise HTTPException(404, "Model nie znaleziony")
    if not job.is_paid or not job.price_cents or job.price_cents <= 0:
        raise HTTPException(400, "Model nie jest platny")
    if user and job.user_id == user.id:
        raise HTTPException(400, "Nie mozesz kupic wlasnego modelu")
    amount = int(job.price_cents)
    commission = int(round(amount * 0.20))
    payout = amount - commission

    # If no Stripe key configured, return mock success (for dev)
    if not settings.STRIPE_SECRET_KEY:
        sale = models.Sale(job_id=job.id, seller_id=job.user_id or 1, buyer_id=user.id if user else None, amount_cents=amount, commission_cents=commission, seller_payout_cents=payout, status="pending")
        db.add(sale); db.commit(); db.refresh(sale)
        # auto-complete in dev
        sale.status="completed"
        db.commit()
        return {"ok": True, "mock": True, "sale_id": sale.id, "message": "Zakup zaliczony (tryb dev bez Stripe). Plik dostepny do pobrania."}

    # Stripe Checkout
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": settings.STRIPE_CURRENCY or "usd", "product_data": {"name": job.title or job.original_filename}, "unit_amount": amount}, "quantity": 1}],
            mode="payment",
            success_url=f"{settings.APP_URL}/u/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.APP_URL}/u/cancel",
            metadata={"job_id": str(job.id), "buyer_id": str(user.id if user else ""), "commission": str(commission)},
        )
        sale = models.Sale(job_id=job.id, seller_id=job.user_id or 1, buyer_id=user.id if user else None, amount_cents=amount, commission_cents=commission, seller_payout_cents=payout, stripe_session_id=session.id, status="pending")
        db.add(sale); db.commit()
        return {"ok": True, "checkout_url": session.url}
    except Exception as e:
        raise HTTPException(500, f"Stripe error: {e}")

@router.get("/{job_id}/sales/me")
def my_sales(job_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401)
    # seller view
    sales = db.query(models.Sale).filter(models.Sale.job_id==job_id, models.Sale.seller_id==user.id).order_by(models.Sale.created_at.desc()).all()
    # buyer view also
    if not sales:
        sales = db.query(models.Sale).filter(models.Sale.job_id==job_id, models.Sale.buyer_id==user.id).all()
    return [{"id":s.id,"amount_cents":s.amount_cents,"commission_cents":s.commission_cents,"status":s.status,"created_at":str(s.created_at)} for s in sales]
