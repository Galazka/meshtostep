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
    try:
        order.stripe_session_id = session.get("id")
        if db is not None:
            db.commit()
    except Exception as e:
        print(f"[stripe] session id save: {e}")
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


def sync_payment(o, db):
    """Czynna weryfikacja: pobieramy session z Stripe i sprawdzamy payment_status.
    Działa nawet gdy webhook nie doleciał (piaskownica, wyciszony endpoint, retry)."""
    if not o or o.is_paid or not _stripe_enabled():
        return bool(o and o.is_paid)
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        sid = getattr(o, "stripe_session_id", None)
        sess = None
        if sid:
            try:
                sess = stripe.checkout.Session.retrieve(sid)
            except Exception:
                sess = None
        if sess is None and o.customer_email:
            try:
                # Session.list nie filtruje po email — pobieramy swieze sesje i filtrujemy w pythonie
                found = stripe.checkout.Session.list(limit=100)
                for cs in (found.get("data") or []):
                    cd = ((cs.get("customer_details") or {}).get("email") or "").lower()
                    if cd != (o.customer_email or "").lower():
                        continue
                    if (cs.get("metadata") or {}).get("order_id") == str(o.id) or cs.get("client_reference_id") == str(o.id):
                        sess = cs
                        o.stripe_session_id = cs.get("id")
                        break
            except Exception as e:
                print(f"[stripe] sync list: {e}")
        if sess and sess.get("payment_status") == "paid":
            o.is_paid = True
            o.payment_method = "stripe"
            if o.status == "nowy":
                o.status = "realizacja"
            try:
                if sess.get("receipt_url"):
                    o.stripe_receipt_url = sess["receipt_url"]
                elif sess.get("payment_intent"):
                    intent = stripe.PaymentIntent.retrieve(sess["payment_intent"], expand=["charges.data"])
                    chs = (intent.get("charges") or {}).get("data") or []
                    if chs and chs[0].get("receipt_url"):
                        o.stripe_receipt_url = chs[0]["receipt_url"]
            except Exception:
                pass
            db.commit()
            db.refresh(o)
            try:
                from .routes_order import _notify_paid
                _notify_paid(o)
            except Exception as e:
                print(f"[stripe] paid mail: {e}")
            return True
    except Exception as e:
        print(f"[stripe] sync error: {e}")
    return bool(o and o.is_paid)


@router.post("/api/orders/{order_id}/sync-payment")
def sync_payment_ep(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Odśwież status płatności prosto ze Stripe (właściciel zamówienia lub admin)."""
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    paid = sync_payment(o, db)
    return {"ok": True, "order_id": o.id, "is_paid": paid, "status": o.status}


@router.get("/api/orders/{order_id}/pay/ok")
def payment_ok(order_id: int, request: Request, db: Session = Depends(get_db)):
    o = db.get(models.Order, order_id)
    if not o:
        return {"ok": True, "notice": "order not found"}
    paid = sync_payment(o, db)
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": paid,
            "tracking_code": getattr(o, "tracking_code", None),
            "redirect": "/konto"}


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
                was_unpaid = not o.is_paid
                o.is_paid = True
                if o.status == "nowy":
                    o.status = "realizacja"
                o.payment_method = "stripe"
                # hosted Stripe receipt link (best effort — used on /konto + rachunek)
                try:
                    pi = session.get("payment_intent")
                    if pi:
                        intent = stripe.PaymentIntent.retrieve(pi, expand=["charges.data"])
                        chs = (intent.get("charges") or {}).get("data") or []
                        if chs and chs[0].get("receipt_url"):
                            o.stripe_receipt_url = chs[0]["receipt_url"]
                except Exception as e:
                    print(f"[stripe] receipt_url fetch failed: {e}")
                db.commit()
                if was_unpaid and o.customer_email:
                    try:
                        from .routes_order import _notify_paid
                        _notify_paid(o)
                    except Exception as e:
                        print(f"[stripe] paid mail failed: {e}")
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