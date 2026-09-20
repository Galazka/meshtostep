"""Stripe Checkout integration for print orders.

If STRIPE_SECRET_KEY is set: creates Checkout Session and returns redirect URL.
If empty: falls backto blik_info (existing behavior) so the app keeps working without keys..
"""
import json
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from . import models
from .config import settings

router = APIRouter()


def _stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY.strip())


def _stripe_session_url(order, db) -> str | None:
    try:
        return _stripe_build_session(order, db)
    except Exception as e:
        db.rollback()
        print(f"[stripe] session create error: {e}")
        return None


def _stripe_build_session(order, db=None):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    currency = (order.currency or "PLN").lower()
    total_pln = float(order.total or 0)
    ship_pln = float(order.shipping_cost or 0)
    amount_total = int(round(total_pln * 100))
    if amount_total < 50:  # Stripe min 0.50
        amount_total = 50
    prod_amount = max(0, int(round((total_pln - ship_pln) * 100)))
    ship_amount = amount_total - prod_amount
    success_url = settings.APP_URL or "https://3dfile.link"
    line_items = []
    if prod_amount > 0:
        line_items.append({
            "price_data": {
                "currency": currency,
                "product_data": {
                    "name": "Wydruk modeli 3D (material, kolory, uslugi) — ceny brutto z VAT",
                    "description": f"Zamowienie #{order.id} — 3dfile.link",
                },
                "unit_amount": prod_amount,
            },
            "quantity": 1,
        })
    if ship_amount > 0:
        line_items.append({
            "price_data": {
                "currency": currency,
                "product_data": {"name": "Wysylka + pakowanie"},
                "unit_amount": ship_amount,
            },
            "quantity": 1,
        })
    if not line_items:
        line_items = [{
            "price_data": {
                "currency": currency,
                "product_data": {"name": f"3dfile.link print order #{order.id}"},
                "unit_amount": amount_total,
            },
            "quantity": 1,
        }]
    checkout_params = dict(
        mode="payment",
        line_items=line_items,
        customer_email=order.customer_email or None,
        client_reference_id=str(order.id),
        metadata={"order_id": str(order.id)},
        success_url=success_url + f"/platnosc?status=success&order={order.id}",
        cancel_url=success_url + f"/platnosc?status=cancel&order={order.id}",
    )
    session = stripe.checkout.Session.create(**checkout_params)
    return session["url"] or None


@router.post("/api/orders/{order_id}/checkout")
def create_checkout(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Return Stripe Checkout URL (or BLIK info fallback)."""
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if not _stripe_enabled():
        return {
            "ok": True,
            "checkout_url": None,
            "blik_fallback": True,
            "total": o.total,
            "currency": o.currency or "PLN",
            "blik_code": "123456789",
            "titled": f"3dfile.link #{o.id}",
        }
    url = _stripe_session_url(o, db)
    if not url:
        return {
            "ok": True,
            "checkout_url": None,
            "blik_fallback": True,
            "total": o.total,
            "currency": o.currency or "PLN",
            "blik_code": "123456789",
            "titled": f"3dfile.link #{o.id}",
            "error": "stripe_session_failed",
        }
    return {"ok": True, "checkout_url": url, "blik_fallback": False, "order_id": o.id}


@router.get("/api/orders/{order_id}/pay/ok")
def payment_ok(order_id: int, request: Request, db: Session = Depends(get_db)):
    o = db.get(models.Order, order_id)
    shadow=o
    if not o:
        return {"ok": True, "notice": "order not found"}
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": o.is_paid, "redirect": "/print.html?paid=1"}


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify Stripe signature and mark order paid on 'checkout.session.completed'."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not sig or not settings.STRIPE_WEBHOOK_SECRET:

        return {"ok": False, "error": "webhook not configured"}
    try:
        import stripe
    except ImportError:
        return {"ok": False, "error": "stripe sdk missing"}
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signature mismatch: {e}")
    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        order_id = None
        try:
            order_id = int((session.get("client_reference_id") or session.get("metadata", {}).get("order_id", "0")) or 0)
        except (TypeError, ValueError):
            order_id = None
        if order_id:
            o = db.get(models.Order, order_id)
            if o:
                o.is_paid = True
                if o.status == "nowy" and not o.status:
                    o.status = "realizacja"
                o.payment_method = "stripe"
                db.commit()
    return {"ok": True}


@router.get("/api/orders/{order_id}/pay")
def get_payment_info(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Payment info - Stripe URL if enabled, else BLIK details."""
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if _stripe_enabled():
        url = _stripe_session_url(o, db)
        return {"ok": True, "order_id": o.id, "total": o.total, "currency": o.currency or "PLN", "checkout_url": url}
    return {
        "ok": True,
        "order_id": o.id,
        "total": o.total,
        "currency": o.currency or "PLN",
        "blik_code": "123456789",
        "bank_name": "mBank",
        "titled": f"3dfile.link #{o.id}",
    }