"""Stripe payments: credit packs, checkout sessions, webhook -> credits."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .auth import require_user
from .config import settings
from .database import get_db

router = APIRouter(prefix="/api", tags=["payments"])


class CheckoutIn(BaseModel):
    pack_id: int


def _stripe():
    try:
        import stripe
    except ImportError:
        raise HTTPException(503, "Stripe SDK missing: pip install stripe")
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        raise HTTPException(503, "STRIPE_SECRET_KEY nie ustawiony (zobacz .env.example)")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """List active credit packs (public)."""
    packs = (
        db.query(models.CreditPack)
        .filter(models.CreditPack.is_active == True)  # noqa: E712
        .order_by(models.CreditPack.id)
        .all()
    )
    return [
        {"id": p.id, "name": p.name, "credits": p.credits, "price_usd": p.price_usd}
        for p in packs
    ]


@router.post("/payments/checkout")
def create_checkout(
    body: CheckoutIn,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for a credit pack. Returns redirect URL."""
    stripe = _stripe()
    pack = (
        db.query(models.CreditPack)
        .filter(models.CreditPack.id == body.pack_id, models.CreditPack.is_active == True)  # noqa: E712
        .first()
    )
    if not pack:
        raise HTTPException(404, "Pakiet nie istnieje")

    amount_cents = int(round(pack.price_usd * 100))
    if amount_cents < 1:
        raise HTTPException(400, "Nieprawidłowa cena pakietu")

    payment = models.Payment(
        user_id=user.id,
        pack_id=pack.id,
        amount_usd=pack.price_usd,
        credits_granted=pack.credits,
        status="pending",
        payment_method="stripe",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": getattr(settings, "STRIPE_CURRENCY", "usd") or "usd",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": f"MeshToStep — {pack.name} ({pack.credits} credits)"
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "user_id": str(user.id),
                "pack_id": str(pack.id),
                "payment_id": str(payment.id),
            },
            success_url=f"{settings.APP_URL}/?payment=ok",
            cancel_url=f"{settings.APP_URL}/?payment=cancel",
        )
    except Exception as e:
        payment.status = "failed"
        db.commit()
        raise HTTPException(502, f"Stripe error: {e}")

    payment.reference = session.id
    db.commit()
    return {"url": session.url, "session_id": session.id}


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook: on checkout.session.completed grant credits. Idempotent."""
    raw = await request.body()
    try:
        import stripe  # noqa: F401

        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
        if secret:
            import stripe as _s

            event = _s.Webhook.construct_event(
                raw, request.headers.get("stripe-signature", ""), secret
            )
        else:
            event = json.loads(raw.decode() or "{}")
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    if isinstance(event, dict):
        etype = event.get("type", "")
        obj = (event.get("data", {}) or {}).get("object", {}) or {}
    else:  # stripe SDK object (dict subclass normally, fallback)
        etype = event.get("type", "")
        obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        sess_id = obj.get("id", "")
        meta = obj.get("metadata", {}) or {}
        payment = None
        if meta.get("payment_id"):
            try:
                payment = (
                    db.query(models.Payment)
                    .filter(models.Payment.id == int(meta["payment_id"]))
                    .first()
                )
            except (ValueError, TypeError):
                payment = None
        if payment is None and sess_id:
            payment = (
                db.query(models.Payment)
                .filter(models.Payment.reference == sess_id)
                .first()
            )
        if payment is not None and payment.status != "completed":
            user = (
                db.query(models.User)
                .filter(models.User.id == payment.user_id)
                .first()
            )
            pack = (
                db.query(models.CreditPack)
                .filter(models.CreditPack.id == payment.pack_id)
                .first()
            )
            credits = pack.credits if pack else (payment.credits_granted or 0)
            if user:
                user.credits = (user.credits or 0) + credits
            payment.status = "completed"
            payment.credits_granted = credits
            if not payment.reference:
                payment.reference = sess_id
            db.commit()

    return {"ok": True}
