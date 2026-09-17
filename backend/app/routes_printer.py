"""Print marketplace routes: requests, offers, reviews. — 3dfile.link"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user, require_user
from .database import get_db
from .config import settings

router = APIRouter()


@router.post("/api/print/requests")
def create_print_request(
    request: Request,
    title: str = Form(..., min_length=3, max_length=200),
    description: str = Form(None),
    material: str = Form("PLA"),
    quantity: int = Form(1, ge=1),
    city: str = Form(None),
    budget_pln: float = Form(None, ge=0),
    deadline: str = Form(None),
    auction_hours: int = Form(48, ge=1, le=168),
    job_uuid: str = Form(None),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    """Create a print request. Auto-auction_end defaults to 48h."""
    auction_end = datetime.utcnow() + timedelta(hours=auction_hours)

    # optional attached model
    job_id = None
    if job_uuid:
        job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
        if not job:
            raise HTTPException(404, "Model not found")
        job_id = job.id

    pr = models.PrintRequest(
        user_id=user.id,
        job_id=job_id,
        title=title,
        description=description,
        material=material[:30],
        quantity=quantity,
        city=city[:100] if city else None,
        budget_pln=budget_pln,
        deadline=datetime.fromisoformat(deadline) if deadline else None,
        auction_end=auction_end,
        status="open",
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return {"ok": True, "request_id": pr.id, "auction_end": pr.auction_end.isoformat()}


@router.get("/api/print/requests")
def list_print_requests(
    request: Request,
    city: str = None,
    material: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List open print requests (anyone). Sorted by creation date desc."""
    q = db.query(models.PrintRequest).filter(models.PrintRequest.status == "open")
    if city:
        q = q.filter(models.PrintRequest.city.ilike(f"%{city}%"))
    if material:
        q = q.filter(models.PrintRequest.material == material)
    q = q.order_by(models.PrintRequest.created_at.desc()).limit(limit)
    rows = []
    for pr in q.all():
        rows.append({
            "id": pr.id,
            "title": pr.title,
            "description": pr.description,
            "material": pr.material,
            "quantity": pr.quantity,
            "city": pr.city,
            "budget_pln": pr.budget_pln,
            "deadline": pr.deadline.isoformat() if pr.deadline else None,
            "auction_end": pr.auction_end.isoformat() if pr.auction_end else None,
            "offer_count": len(pr.offers),
            "created_at": pr.created_at.isoformat(),
            "owner_username": pr.user.username if pr.user else None,
        })
    return {"ok": True, "requests": rows}


@router.get("/api/print/requests/{request_id}")
def get_print_request(request_id: int, request: Request, db: Session = Depends(get_db)):
    pr = db.get(models.PrintRequest, request_id)
    if not pr or pr.status != "open":
        raise HTTPException(404, "Request not found or closed")
    offers = []
    auction_end = pr.auction_end
    is_owner = False
    user_id = getattr(getattr(request.state, 'user', None), 'id', None) if hasattr(request.state, 'user') else None
    try:
        from .auth import get_current_user_optional
        user = get_current_user_optional(request, db)
        if user and user.id == pr.user_id:
            is_owner = True
        user_id = user.id if user else None
    except Exception:
        pass
    # show offers only to owner or after auction_end
    show_all = is_owner or (auction_end and datetime.utcnow() >= auction_end)
    for o in pr.offers:
        if show_all or o.user_id == user_id:
            offers.append({
                "id": o.id,
                "price_pln": o.price_pln,
                "days": o.days,
                "message": o.message,
                "shipping_method": o.shipping_method,
                "rating": o.rating,
                "rating_count": o.rating_count,
                "created_at": o.created_at.isoformat(),
                "is_owner": o.user_id == user_id,
            })
    return {"ok": True, "request": {
        "id": pr.id,
        "title": pr.title,
        "description": pr.description,
        "material": pr.material,
        "quantity": pr.quantity,
        "city": pr.city,
        "budget_pln": pr.budget_pln,
        "deadline": pr.deadline.isoformat() if pr.deadline else None,
        "auction_end": pr.auction_end.isoformat() if pr.auction_end else None,
        "owner_username": pr.user.username if pr.user else None,
        "offers": offers,
    }}


@router.get("/api/print/requests/{request_id}/offers")
def list_offers(request_id: int, request: Request, db: Session = Depends(get_db)):
    pr = db.get(models.PrintRequest, request_id)
    if not pr or pr.status != "open":
        raise HTTPException(404, "Request not found")
    # hide offers until auction_end unless owner
    try:
        user = None
        from .auth import get_current_user_optional
        user = get_current_user_optional(request, db)
        is_owner = bool(user and user.id == pr.user_id)
    except Exception:
        is_owner = False
    if not is_owner and pr.auction_end and datetime.utcnow() < pr.auction_end:
        raise HTTPException(403, "Offers hidden until auction ends")
    rows = [{
        "id": o.id,
        "printer_username": o.user.username if o.user else None,
        "price_pln": o.price_pln,
        "days": o.days,
        "message": o.message,
        "shipping_method": o.shipping_method,
        "rating": o.rating,
        "rating_count": o.rating_count,
        "created_at": o.created_at.isoformat(),
        "is_owner": bool(user and o.user_id == user.id),
    } for o in pr.offers]
    return {"ok": True, "offers": rows}


@router.post("/api/print/requests/{request_id}/offers")
def create_offer(
    request_id: int,
    request: Request,
    price_pln: float = Form(..., ge=0),
    days: int = Form(None, ge=1),
    message: str = Form(None),
    shipping_method: str = Form("pickup"),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = db.get(models.PrintRequest, request_id)
    if not pr or pr.status != "open":
        raise HTTPException(404, "Request not found or closed")
    if pr.user_id == user.id:
        raise HTTPException(400, "Owner cannot bid on own request")
    # hide bids until auction end — still allow placing
    if not user.has_printer and user.role not in ("printer", "both"):
        raise HTTPException(403, "Only users with a printer can place offers")
    offer = models.PrintOffer(
        request_id=pr.id,
        user_id=user.id,
        price_pln=price_pln,
        days=days,
        message=message,
        shipping_method=shipping_method[:20],
        status="pending",
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return {"ok": True, "offer_id": offer.id}


@router.post("/api/print/offers/{offer_id}/accept")
def accept_offer(offer_id: int, request: Request, db: Session = Depends(get_db)):
    offer = db.get(models.PrintOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Offer not found")
    user = None
    from .auth import get_current_user_optional
    user = get_current_user_optional(request, db)
    if not user or offer.request.user_id != user.id:
        raise HTTPException(403, "Only request owner can accept")
    # mark this offer accepted, others rejected
    for o in offer.request.offers:
        o.status = "accepted" if o.id == offer.id else "rejected"
    offer.request.status = "closed"
    db.commit()
    return {"ok": True, "accepted_offer_id": offer.id}


@router.post("/api/print/offers/{offer_id}/reviews")
def create_review(
    offer_id: int,
    request: Request,
    rating: int = Form(..., ge=1, le=5),
    text: str = Form(None),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    offer = db.get(models.PrintOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Offer not found")
    if offer.request.user_id != user.id:
        raise HTTPException(403, "Only request owner can review this offer")
    # avg update on printer
    printer = offer.user  # printer = User who owns offer
    cur_n = printer.rating_count or 0
    cur_avg = printer.rating_avg or 0.0
    new_n = cur_n + 1
    new_avg = (cur_avg * cur_n + rating) / new_n
    printer.rating_count = new_n
    printer.rating_avg = round(new_avg, 2)
    offer.rating = round((offer.rating or 0.0) * 0 + rating, 1) if not offer.rating else round((offer.rating * offer.rating_count + rating) / (offer.rating_count + 1), 2)
    offer.rating_count = (offer.rating_count or 0) + 1
    review = models.JobReview(
        offer_id=offer.id,
        reviewer_id=user.id,
        rating=rating,
        text=text,
    )
    db.add(review)
    db.commit()
    db.refresh(offer)
    db.refresh(printer)
    return {"ok": True, "printer_rating_avg": printer.rating_avg, "printer_rating_count": printer.rating_count}


# --- optional auth helper ---
def get_current_user_optional(request: Request, db: Session):
    """Return user if JWT present & valid, else None. Non-raising."""
    from .auth import decode_token
    token = request.cookies.get("token") or None
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        payload = decode_token(token)
        return db.get(models.User, payload.get("sub"))
    except Exception:
        return None
