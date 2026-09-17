"""Order management + automated pricing. — 3dfile.link"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models
from .auth import get_current_user, require_user
from .database import get_db
from .config import settings

router = APIRouter()

# Material prices PLN/kg (2026, bulk from Polish suppliers)
MATERIAL_PRICES = {
    "PLA": 89.0, "PLA HT": 120.0, "PLA CF": 140.0,
    "PETG": 110.0, "PETG FR": 150.0,
    "ABS": 95.0, "ASA": 120.0, "ASA CF": 180.0,
    "TPU": 130.0, "TPU 75D": 150.0,
    "PA12 CF": 220.0, "PA12": 180.0,
    "PCTG": 140.0,
    "Iglidur I150PF": 450.0, "Iglidur I180PF": 480.0, "Iglidur I190PF": 520.0,
    "PLA Matte": 100.0, "PLA Silk": 110.0, "PLA Glow": 130.0,
}

# Dye/color premium per material
COLOR_PREMIUM = {
    "natural": 0.0, "black": 0.0, "white": 0.0,
    "blue": 5.0, "red": 5.0, "green": 5.0, "yellow": 5.0,
    "orange": 7.0, "purple": 7.0, "pink": 7.0,
    "gray": 3.0, "silver": 10.0, "gold": 15.0,
    "carbon": 20.0, "wood": 15.0, "brass": 25.0,
}

SHIPPING = {
    "standard": {"PL": 15.0, "EU": 35.0, "GLOBAL": 55.0},
    "express": {"PL": 25.0, "EU": 55.0, "GLOBAL": 85.0},
    "priority": {"PL": 40.0, "EU": 80.0, "GLOBAL": 130.0},
    "pickup": {"PL": 0.0, "EU": 0.0, "GLOBAL": 0.0},
}

# Printer electricity 150W typical; cost per kWh PLN
DEFAULT_WATTS = 150
DEFAULT_KWH = 1.15

# Global margin percentage (Tom's markup on print cost)
MARGIN_PERCENT = getattr(settings, "print_margin_percent", 68)


def get_material_price(material: str) -> float:
    return MATERIAL_PRICES.get(material, 110.0)  # fallback PETG


def estimate_print_time_hours(volume_cm3: float, material: str = "PLA") -> float:
    """Very rough: speed ~ 60 mm/s, layer 0.2mm, ~100mm³/s throughput."""
    if not volume_cm3 or volume_cm3 <= 0:
        return 2.0
    mm3 = volume_cm3 * 1000
    throughput = 100 if material in ("PLA", "PETG") else 80 if material in ("ABS", "ASA", "TPU") else 60
    return max(0.5, mm3 / (throughput * 3600))


def estimate_filament_grams(volume_cm3: float, material: str = "PLA") -> float:
    """Density in g/cm³: PLA 1.24, PETG 1.27, ABS 1.04, PA12 1.14, TPU 1.2."""
    densities = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.06,
                 "PA12": 1.14, "TPU": 1.20, "PCTG": 1.27, "Iglidur I150PF": 1.42}
    density = densities.get(material, 1.24)
    return volume_cm3 * density if volume_cm3 else 0


@router.post("/api/calculate")
def calculate_price(
    material: str = Form("PLA"),
    color: str = Form("natural"),
    quantity: int = Form(1, ge=1),
    shipping: str = Form("standard"),
    shipping_region: str = Form("PL"),
    volume_cm3: float = Form(0),
    estimated_hours: float = Form(0),
):
    """Automated pricing. Returns cost breakdown + total with margin."""
    mat_price_kg = get_material_price(material)
    filament_g = estimate_filament_grams(volume_cm3, material) if volume_cm3 else None
    filament_cost = 0.0
    if filament_g:
        filament_cost = (filament_g / 1000) * mat_price_kg * quantity
    else:
        # rough fallback: assume 200g for small objects
        filament_g = 200
        filament_cost = (filament_g / 1000) * mat_price_kg * quantity

    hours = max(estimated_hours, estimate_print_time_hours(volume_cm3, material))
    power_cost = (DEFAULT_WATTS / 1000) * hours * DEFAULT_KWH

    color_premium = COLOR_PREMIUM.get(color, 0.0) * quantity

    shipping_cost = SHIPPING.get(shipping, SHIPPING["standard"]).get(shipping_region, SHIPPING["standard"]["PL"])

    subtotal = filament_cost + power_cost + color_premium
    margin = subtotal * (MARGIN_PERCENT / 100)
    total = subtotal + margin + shipping_cost

    return {
        "ok": True,
        "breakdown": {
            "filament_g": round(filament_g, 1),
            "filament_cost": round(filament_cost, 2),
            "power_cost": round(power_cost, 2),
            "color_premium": round(color_premium, 2),
            "printing_hours": round(hours, 2),
            "material": material,
            "color": color,
            "quantity": quantity,
            "shipping_region": shipping_region,
            "shipping_method": shipping,
            "shipping_cost": round(shipping_cost, 2),
        },
        "pricing": {
            "subtotal": round(subtotal, 2),
            "margin_pln": round(margin, 2),
            "margin_percent": MARGIN_PERCENT,
            "shipping": round(shipping_cost, 2),
            "total": round(total, 2),
            "total_display": f"{round(total, 2):.2f} PLN",
        },
    }


# ---- Orders ----

@router.post("/api/orders")
def create_order(
    request: Request,
    job_id: int = Form(None, ge=1),
    job_uuid: str = Form(None),
    name: str = Form(..., min_length=2, max_length=100),
    email: str = Form(...),
    phone: str = Form(None),
    address: str = Form(None),
    city: str = Form(None),
    postal_code: str = Form(None),
    country: str = Form("PL"),
    material: str = Form("PLA"),
    color: str = Form("natural"),
    quantity: int = Form(1, ge=1),
    shipping: str = Form("standard"),
    shipping_region: str = Form("PL"),
    estimated_hours: float = Form(0),
    volume_cm3: float = Form(0),
    notes: str = Form(None),
    payment_method: str = Form("blik"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create order — user can be logged-in or anonymous (email required)."""
    # price from calculate
    mat_price_kg = get_material_price(material)
    filament_g = estimate_filament_grams(volume_cm3, material) if volume_cm3 else 200
    filament_cost = (filament_g / 1000) * mat_price_kg * quantity
    hours = max(estimated_hours, estimate_print_time_hours(volume_cm3, material))
    power_cost = (DEFAULT_WATTS / 1000) * hours * DEFAULT_KWH
    color_premium = COLOR_PREMIUM.get(color, 0.0) * quantity
    shipping_cost = SHIPPING.get(shipping, SHIPPING["standard"]).get(shipping_region, SHIPPING["standard"]["PL"])
    subtotal = filament_cost + power_cost + color_premium
    margin = subtotal * (MARGIN_PERCENT / 100)
    total = subtotal + margin + shipping_cost

    order = models.Order(
        user_id=user.id if user else None,
        job_id=job_id,
        job_uuid=job_uuid,
        customer_name=name[:100],
        customer_email=email[:255],
        customer_phone=phone[:30] if phone else None,
        customer_address=address[:500] if address else None,
        customer_city=city[:100] if city else None,
        customer_postal=postal_code[:20] if postal_code else None,
        customer_country=country[:30],
        material=material[:30],
        color=color[:20],
        quantity=quantity,
        shipping_method=shipping[:20],
        shipping_region=shipping_region[:20],
        estimated_hours=round(hours, 2),
        volume_cm3=round(volume_cm3, 2),
        filament_grams=round(filament_g, 1),
        printing_hours=round(hours, 2),
        notes=notes[:2000] if notes else None,
        payment_method=payment_method[:20],
        subtotal=round(subtotal, 2),
        margin_pln=round(margin, 2),
        shipping_cost=round(shipping_cost, 2),
        total=round(total, 2),
        status="nowy",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"ok": True, "order_id": order.id, "total": order.total, "estimate": round(total, 2)}


@router.get("/api/orders")
def list_orders(
    request: Request,
    status: str = None,
    country: str = None,
    material: str = None,
    paid: bool = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Admin: list all orders sorted desc by id."""
    q = db.query(models.Order)
    if status:
        q = q.filter(models.Order.status == status)
    if paid is not None:
        q = q.filter(models.Order.is_paid == paid)
    if country:
        q = q.filter(models.Order.customer_country == country)
    if material:
        q = q.filter(models.Order.material == material)
    rows = []
    for o in q.order_by(models.Order.id.desc()).limit(limit).all():
        rows.append({
            "id": o.id, "job_id": o.job_id, "job_uuid": o.job_uuid,
            "customer_name": o.customer_name, "customer_email": o.customer_email,
            "customer_phone": o.customer_phone, "customer_city": o.customer_city,
            "customer_country": o.customer_country,
            "material": o.material, "color": o.color, "quantity": o.quantity,
            "shipping_method": o.shipping_method, "shipping_region": o.shipping_region,
            "filament_grams": o.filament_grams, "printing_hours": o.printing_hours,
            "volume_cm3": o.volume_cm3,
            "subtotal": o.subtotal, "margin_pln": o.margin_pln,
            "shipping_cost": o.shipping_cost, "total": o.total,
            "status": o.status, "is_paid": o.is_paid, "payment_method": o.payment_method,
            "notes": o.notes,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return {"ok": True, "orders": rows, "total": len(rows)}


@router.get("/api/orders/stats")
def order_stats(db: Session = Depends(get_db)):
    """Dashboard stats."""
    total = db.query(models.Order).count()
    paid_count = db.query(models.Order).filter(models.Order.is_paid == True).count()
    total_revenue = db.query(models.Order).filter(models.Order.is_paid == True).with_entities(
        models.Order.total).all()
    revenue = sum((r[0] or 0) for r in total_revenue)
    by_status = db.query(models.Order.status, func.count(models.Order.id)).group_by(models.Order.status).all()
    by_country = db.query(models.Order.customer_country, func.count(models.Order.id)).group_by(models.Order.customer_country).all()
    by_material = db.query(models.Order.material, func.count(models.Order.id)).group_by(models.Order.material).all()
    return {"ok": True, "stats": {
        "total_orders": total,
        "paid_orders": paid_count,
        "unpaid_orders": total - paid_count,
        "total_revenue_pln": round(revenue, 2),
        "by_status": [{ "status": s, "count": c } for s, c in by_status],
        "by_country": [{ "country": c, "count": n } for c, n in by_country],
        "by_material": [{ "material": m, "count": n } for m, n in by_material],
    }}


@router.patch("/api/orders/{order_id}")
def update_order(
    order_id: int,
    request: Request,
    status: str = Form(None),
    is_paid: bool = Form(None),
    shipping_method: str = Form(None),
    payment_method: str = Form(None),
    notes: str = Form(None),
    admin=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patch order fields. Admin only."""
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, "Admin only")
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    if status:
        valid = {"nowy", "wycena", "realizacja", "wysłano", "zrealizowano", "anulowano"}
        if status not in valid:
            raise HTTPException(400, f"Invalid status: {status}")
        o.status = status
    if is_paid is not None:
        o.is_paid = bool(is_paid)
    if shipping_method:
        o.shipping_method = shipping_method[:20]
    if payment_method:
        o.payment_method = payment_method[:20]
    if notes is not None:
        o.notes = notes[:2000] if notes else None
    from datetime import datetime as _dt
    o.updated_at = _dt.utcnow()
    db.commit()
    db.refresh(o)
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": o.is_paid}
