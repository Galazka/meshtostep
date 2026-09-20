"""Order management + automated print-on-demand pricing. — 3dfile.link

Pricing logic:
  • Models larger than 25×25 mm (workable bed) are split into parts — each part
    priced independently (filament volume scaled down, but fixed per-part
    overhead: +0.5 h print time).
  • calculate_price() returns a public cart breakdown (only shipping + product
    total is visible; filament/electricity/margin are internal).
  • /api/orders/{id}/costs returns the full internal cost sheet — admin only.
  • All rates editable from admin panel via /api/admin/pricing (stored in
    PricingConfig table).
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_

from . import models
from pydantic import BaseModel
from .auth import get_current_user, require_user, require_admin
from .database import get_db
from .config import settings

router = APIRouter()

# —— Multi-currency config endpoint (K3) ——
@router.get("/api/config/currencies")
def get_currencies():
    """Public currency config — rates cached in env, no API key."""
    return {
        "ok": True,
        "base": "PLN",
        "rates": {
            "PLN": {"code": "PLN", "symbol": "zł", "rate": 1.0, "name": "Złoty"},
            "USD": {"code": "USD", "symbol": "$", "rate": settings.currency_rate_usd, "name": "Dollar"},
            "EUR": {"code": "EUR", "symbol": "€", "rate": settings.currency_rate_eur, "name": "Euro"},
        },
    }

# ── Material & cost constants (defaults; overridden by PricingConfig rows) ──
DEFAULT_MATERIAL_PRICES = {
    "PLA": 79.0, "PLA HT": 120.0, "PLA CF": 199.0,
    "PETG": 95.0, "PETG HF": 129.0, "PETG FR": 150.0,
    "ABS": 89.0, "ASA": 159.0, "ASA CF": 299.0,
    "TPU": 130.0,
    "PLA Matte": 100.0, "PLA Silk": 110.0, "PLA Glow": 130.0,
}

DEFAULT_COLOR_PREMIUM = {
    "natural": 0.0, "black": 0.0, "white": 0.0,
    "blue": 5.0, "red": 5.0, "green": 5.0, "yellow": 5.0,
    "orange": 7.0, "purple": 7.0, "pink": 7.0,
    "gray": 3.0, "silver": 10.0, "gold": 15.0,
    "carbon": 20.0, "wood": 15.0, "brass": 25.0,
}

# InPost 2026: Paczkomat gabaryt A 16,49 zł. Standard = 5 dni (normalna cena).
# Ekspres = 2 dni, ale x2 (Tom potrzebuje czasu na wydruki / kolejkowanie).
DEFAULT_SHIPPING = {
    "standard":  {"PL": 16.49, "EU": 35.0, "GLOBAL": 55.0},
    "express":   {"PL": 33.00, "EU": 70.0, "GLOBAL": 110.0},
    "priority":  {"PL": 40.99, "EU": 95.0, "GLOBAL": 160.0},
    "pickup":    {"PL": 0.0,   "EU": 0.0,  "GLOBAL": 0.0},
    "pickup_express": {"PL": 19.00, "EU": 19.00, "GLOBAL": 19.00},
}

DEFAULT_WATTS = 150
DEFAULT_KWH = getattr(settings, "kwh_price", 1.50)  # Bamboo P1S ~1.5 zł/kWh
PACKING_FEE_PLN = 3.0  # karton + etykieta + folia na przesyłkę (InPost Paczkomat)
PICKUP_EXPRESS_FEE_PLN = 19.00  # odbiór osobisty ekspres: priorytet w kolejce, gotowe do 2 dni roboczych (opłata all-inclusive)
FREE_SHIPPING_MIN_PLN = 200.0  # zamówienia >=200 zł → wysyłka gratis (Tom pokrywa koszt)

# ── Małe zamówienia: promocyjna wysyłka (Tom dopłaca różnicę z marży — konkurencyjny pricing) ──
SMALL_ORDER_MAX_PRODUCT = 40.0   # poniżej tej kwoty PRODUKTU obowiązuje flat
SMALL_ORDER_SHIP_FLAT = 9.90     # wysyłka+pakowanie ŁĄCZNIE (normalnie InPost 16.49 + packing 3.00 = 19.49)

def _apply_small_order_shipping(product_pln: float, shipping_cost: float, shipping: str) -> float:
    """Małe zamówienia (<25 zł produktu, nie pickup): wysyłka+pakowanie flat 11.90 zł.
    Bez tego mały model 6 cm³ kosztowałby 26 zł (wysyłka zjada 80% ceny)."""
    if shipping_cost > 0 and shipping not in ("pickup", "pickup_express") and product_pln < SMALL_ORDER_MAX_PRODUCT:
        return min(shipping_cost, SMALL_ORDER_SHIP_FLAT)
    return shipping_cost
MARGIN_PERCENT = getattr(settings, "print_margin_percent", 68)
MAX_PART_AREA_MM2 = 65536  # 256×256 mm build (Bamboo P1S)
DENSITIES = {
    "PLA": 1.24, "PLA HT": 1.24, "PLA CF": 1.24,
    "PLA Matte": 1.24, "PLA Silk": 1.24, "PLA Glow": 1.24,
    "PETG": 1.27, "PETG HF": 1.27, "PETG FR": 1.28,
    "ABS": 1.04, "ASA": 1.07, "ASA CF": 1.15,
    "TPU": 1.20,
}

# — Material descriptions: properties + typical use (shown to customer before ordering) —
MATERIAL_DESCRIPTIONS = {
    "PLA": "Uniwersalny, tani, sztywny. Do prototypów, modeli, osłon i dekoracji. Nie do wysokich temperatur (ugina się ~60°C) ani intensywnej eksploatacji.",
    "PLA HT": "PLA odporny na wyższe temperatury (~90–100°C). Elementy w pobliżu ciepła, osłony LED, uchwyty, prototypy o lepszej wytrzymałości termicznej.",
    "PLA CF": "PLA z włóknem węglowym — sztywniejszy i lżejszy. Części konstrukcyjne, drony, elementy wymagające sztywności bez ciężaru.",
    "PLA Matte": "PLA o matowym, eleganckim wykończeniu. Modele premium, figurki, obudowy, elementy dekoracyjne i prezentowe.",
    "PLA Silk": "PLA o jedwabistym połysku, gładki w dotyku. Bryły, elementy dotykane, dekoracje, prototypy o estetycznym wyglądzie.",
    "PLA Glow": "PLA świecący w ciemności. Figurki, nakładki, breloki, elementy nocne i ozdobne.",
    "PETG": "W połowie przezroczysty, udarny, odporny na uderzenia i chemię. Klosze, osłony, prototypy przezroczyste, elementy narażone na uderzenia.",
    "PETG HF": "PETG wysokiej jakości — lepsza przejrzystość i udarność. Klosze, obudowy, elementy optyczne, modele o dużych powierzchniach przezroczystych.",
    "PETG FR": "PETG niepalny (klasa V-0). Obudowy elektroniczne, elementy w pobliżu źródeł ciepła, zastosowania wymagające norm przeciwpożarowych.",
    "ABS": "Trwały, udarny, klasyk dla przemysłu. Obudowy, uchwyty, prototypy funkcjonalne, elementy mechaniczne wymagające wytrzymałości.",
    "ASA": "Odporny na UV i warunki atmosferyczne (nie żółknie na słońcu). Elementy zewnętrzne, ogrodowe, motoryzacyjne, części narażone na słońce.",
    "ASA CF": "ASA z włóknem węglowym — odporny na UV i sztywny. Elementy zewnętrzne i konstrukcyjne, części motoryzacyjne premium.",
    "TPU": "Elastyczny, gumowy. Uszczelki, ochraniacze, amortyzatory, części giętkie i odporne na ścieranie.",
}


def _cfg(db, key, default):
    """Read a PricingConfig row; fall back to hardcoded default."""
    if db is not None:
        row = db.query(models.PricingConfig).filter(models.PricingConfig.key == key).first()
        if row:
            try:
                if row.kind == "string":
                    return row.value
                return float(row.value)
            except (ValueError, TypeError):
                pass
    # fallback defaults
    if key.startswith("material:"):
        m = key.split(":", 1)[1]
        return DEFAULT_MATERIAL_PRICES.get(m, 110.0)
    if key.startswith("color:"):
        c = key.split(":", 1)[1]
        return DEFAULT_COLOR_PREMIUM.get(c, 0.0)
    if key.startswith("shipping_"):
        parts = key.split(":")
        if len(parts) == 3:
            tier, region = parts[1], parts[2]
            return DEFAULT_SHIPPING.get(tier, DEFAULT_SHIPPING["standard"]).get(region, 15.0)
    if key == "margin_percent":
        return MARGIN_PERCENT
    if key == "watts":
        return DEFAULT_WATTS
    if key == "kwh_pln":
        return DEFAULT_KWH
    if key == "max_part_area_mm2":
        return MAX_PART_AREA_MM2
    if key == "density_default_g_cm3":
        return 1.24
    return default


def _cfg_value(db, tier, region):
    """Shipping cost for tier + region."""
    if db is not None:
        row = db.query(models.PricingConfig).filter(models.PricingConfig.key == f"shipping_{tier}:{region}").first()
        if row:
            try:
                return float(row.value)
            except (ValueError, TypeError):
                pass
    return DEFAULT_SHIPPING.get(tier, DEFAULT_SHIPPING["standard"]).get(region, 15.0)


def get_material_price(material: str, db=None) -> float:
    return _cfg(db, f"material:{material}", DEFAULT_MATERIAL_PRICES.get(material, 110.0))


def estimate_print_time_hours(volume_cm3: float, material: str = "PLA", parts: int = 1) -> float:
    """Very rough: speed ~60 mm/s, layer 0.2 mm, ~100 mm³/s throughput (PLA/PETG)."""
    if not volume_cm3 or volume_cm3 <= 0:
        return 2.0
    mm3 = volume_cm3 * 1000  # całkowita objętość modelu (parts drukowane równolegle)
    throughput = {"PLA": 280, "PETG": 240, "PCTG": 200, "ASA": 220, "ABS": 250}.get(material, 200)
    base = max(0.25, mm3 / (throughput * 3600))
    # fixed per-model setup overhead (not per-part) — Bamboo P1S auto-leveling ~2min
    return base + 0.1


def estimate_filament_grams(volume_cm3: float, material: str = "PLA") -> float:
    """Density in g/cm³: PLA 1.24, PETG 1.27, ABS 1.04, PA12 1.14, TPU 1.2."""
    density = DENSITIES.get(material, 1.24)
    return volume_cm3 * density if volume_cm3 else 0


def _split_into_parts(volume_cm3: float, dims: str = None, db=None) -> int:
    """Models > 25×25 mm (bed) split into parts.

    If `dims` = "X x Y x Z mm" we use XY area.
    Otherwise estimate from volume assuming 20 mm height → area ≈ vol×1000/20.
    """
    max_area = float(_cfg(db, "max_part_area_mm2", MAX_PART_AREA_MM2))
    import re, math
    if dims:
        nums = re.findall(r"[\d.]+", dims.split("mm")[0] if "mm" in dims else dims)
        if len(nums) >= 2:
            try:
                x, y = float(nums[0]), float(nums[1])
                area = x * y
                if area > max_area:
                    return max(1, math.ceil(area / max_area))
            except (ValueError, IndexError):
                pass
    if volume_cm3 and volume_cm3 > 0:
        area_mm2 = (volume_cm3 * 1000) / 20.0  # assume 20 mm height
        if area_mm2 > max_area:
            return max(1, math.ceil(area_mm2 / max_area))
    return 1


def _apply_discount(db, code, product_total):
    """Validate coupon code; return (discount_pln, info_dict)."""
    if not code:
        return 0.0, None
    row = db.execute(text(
        "SELECT code, discount_pln, discount_pct, expires_at, min_order_pln FROM discount_codes WHERE code = :c AND is_active = TRUE"
    ), {"c": code.upper()}).fetchone() if db.bind else None
    if not row:
        return 0.0, None
    code_val, dpln, dpct, exp, min_order = row[0], row[1], row[2], row[3], (row[4] or 0)
    import datetime as _dt
    if exp and exp < _dt.datetime.utcnow():
        return 0.0, None
    if product_total < min_order:
        return 0.0, None
    amount = dpln or 0.0
    if dpct and dpct > 0:
        amount = max(amount, round(product_total * (dpct / 100), 2))
    return round(amount, 2), {"code": code_val, "discount_pln": round(amount, 2), "discount_pct": dpct or 0.0}


def _ceil05(n: float) -> float:
    """Round up to nearest 0.5 (customer-facing pricing)."""
    import math
    return math.ceil(n * 2) / 2 if n else 0.0


def calculate_price(
    material: str = "PLA",
    color: str = "natural",
    quantity: int = 1,
    shipping: str = "standard",
    shipping_region: str = "PL",
    volume_cm3: float = 0,
    estimated_hours: float = 0,
    dims: str = None,
    discount_code: str = None,
    db=None,
    currency: str = "PLN",
):
    """Calculate price. Returns dict with PUBLIC (customer-facing) + INTERNAL cost sheet.

    Public: shipping_cost, total (= product_subtotal + shipping - discount)
    Internal: filament_cost, electricity_cost, color_premium, margin_percent,
              margin_pln, discount_pln, parts
    """
    mat_price_kg = get_material_price(material, db)
    margin_pct = float(_cfg(db, "margin_percent", MARGIN_PERCENT))
    watts = float(_cfg(db, "watts", DEFAULT_WATTS))
    kwh = float(_cfg(db, "kwh_pln", DEFAULT_KWH))

    # auto-derive volume from dims if not provided — NOTE: this is BOUNDING BOX volume (overestimate for hollow/non-solid models)
    # prefer uploading STL for accurate volume; dims-only is a rough upper bound
    import re as _re
    if (not volume_cm3 or volume_cm3 <= 0) and dims:
        nums = _re.findall(r"[\d.]+", dims.split("mm")[0] if "mm" in dims else dims)
        if len(nums) >= 3:
            try:
                x, y, z = float(nums[0]), float(nums[1]), float(nums[2])
                # mm³ → cm³
                auto_vol = (x * y * z) / 1000.0
                if auto_vol > 0:
                    volume_cm3 = auto_vol
            except (ValueError, IndexError):
                pass

    parts = _split_into_parts(volume_cm3, dims, db) if volume_cm3 else 1

    # per-part filament (volume / parts, then grams via density)
    vol_per_part = volume_cm3 / parts if parts > 0 else 0
    filament_g_per = estimate_filament_grams(vol_per_part, material)
    total_filament_g = filament_g_per * parts * quantity
    filament_cost = (total_filament_g / 1000) * mat_price_kg

    hours = max(estimated_hours, estimate_print_time_hours(volume_cm3, material, parts)) if volume_cm3 else max(estimated_hours, 2.0)
    power_cost = (watts / 1000) * hours * kwh
    color_premium = float(_cfg(db, f"color:{color}", DEFAULT_COLOR_PREMIUM.get(color, 0.0))) * quantity

    subtotal = filament_cost + power_cost + color_premium
    margin_pln = round(subtotal * (margin_pct / 100), 2)
    product_total = round(subtotal + margin_pln, 2)  # what customer pays for printing

    shipping_cost = round(_cfg_value(db, shipping, shipping_region), 2)
    # Packing fee (karton, etykieta, folia) — dodawany tylko gdy paczka jest wysyłana,
    # NIE przy odbiorze osobistym. Konfigurowalne: packing_pln (default 5.00).
    packing_fee = 0.0 if shipping in ("pickup", "pickup_express") else float(_cfg(db, "packing_pln", PACKING_FEE_PLN))
    shipping_cost = round(shipping_cost + packing_fee, 2)
    discount_pln = 0.0
    discount_info = None
    if discount_code and db:
        discount_pln, discount_info = _apply_discount(db, discount_code, product_total)

    # minimum order: product must be >= 3 zł
    if product_total < 3.0:
        product_total = 3.0
    # MAŁE ZAMÓWIENIE: flat wysyłka (zanim free-shipping check)
    small_order = shipping_cost > 0 and product_total < SMALL_ORDER_MAX_PRODUCT and shipping not in ("pickup", "pickup_express")
    if small_order:
        shipping_cost = min(shipping_cost, SMALL_ORDER_SHIP_FLAT)
    # FREE SHIPPING: zamówienia >=200 zł (produkt) → wysyłka gratis, Tom pokrywa koszt
    free_shipping = False
    if shipping_cost > 0 and shipping not in ("pickup", "pickup_express") and product_total >= float(_cfg(db, "free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)):
        shipping_cost = 0.0
        free_shipping = True
    pln_total = round(product_total + shipping_cost - discount_pln, 2)

    # round up to nearest 0.5 zł (customer pricing)
    import math as _math
    pln_total = _ceil05(pln_total)
    cur = currency.upper() if currency else "PLN"
    rate = {"USD": settings.currency_rate_usd, "EUR": settings.currency_rate_eur}.get(cur, 1.0)
    total = _ceil05(pln_total / rate if rate else pln_total)
    subtotal_cur = _ceil05(product_total / rate if rate else product_total)
    shipping_cur = _ceil05(shipping_cost / rate if rate else shipping_cost)
    discount_cur = round(discount_pln / rate, 2) if rate else discount_pln

    return {
        # ── klient widzi ──
        "product_subtotal": subtotal_cur,   # druk + marża (ukryta)
        "product_subtotal_pln": product_total,
        "shipping_cost": shipping_cur,
        "shipping_cost_pln": shipping_cost,
        "free_shipping": free_shipping,
        "small_order_shipping": bool(small_order),
        "discount_pln": round(discount_pln, 2),
        "total": total,
        "currency": cur,
        "exchange_rate": rate,
        # ── admin / kosztorys ──
        "internal": {
            "filament_g": round(total_filament_g, 2),
            "filament_cost": round(filament_cost, 2),
            "electricity_cost": round(power_cost, 2),
            "color_premium": round(color_premium, 2),
            "margin_percent": margin_pct,
            "margin_pln": margin_pln,
            "print_parts": parts,
            "print_hours": round(hours, 2),
            "material_price_kg": mat_price_kg,
            "discount_info": discount_info,
        },
        "parts": parts,
    }


@router.post("/api/calculate")
def calculate_price_endpoint(
    material: str = Form("PLA"),
    color: str = Form("natural"),
    quantity: int = Form(1, ge=1),
    shipping: str = Form("standard"),
    shipping_region: str = Form("PL"),
    volume_cm3: float = Form(0),
    estimated_hours: float = Form(0),
    dims: str = Form(None),
    discount_code: str = Form(None),
    currency: str = Form("PLN"),
    db: Session = Depends(get_db),
):
    """Public price calculator — only shows shipping + total to customer."""
    calc = calculate_price(material, color, quantity, shipping, shipping_region,
                           volume_cm3, estimated_hours, dims, discount_code, db, currency)
    return {
        "ok": True,
        "product_subtotal": calc["product_subtotal"],
        "shipping_cost": calc["shipping_cost"],
        "free_shipping": calc["free_shipping"],
        "discount_pln": calc["discount_pln"],
        "total": calc["total"],
        "currency": calc["currency"],
        "exchange_rate": calc["exchange_rate"],
        "parts": calc["parts"],
        "material": material,
        "color": color,
        "quantity": quantity,
        "print_hours": calc["internal"]["print_hours"],
    }


# ---- Orders ----

@router.post("/api/orders")
def create_order(
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
    dims: str = Form(None),
    discount_code: str = Form(None),
    notes: str = Form(None),
    payment_method: str = Form("blik"),
    currency: str = Form("PLN"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create order — user can be logged-in or anonymous (email required)."""
    calc = calculate_price(material, color, quantity, shipping, shipping_region,
                           volume_cm3, estimated_hours, dims, discount_code, db, currency)
    internal = calc["internal"]

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
        color=color[:140],
        quantity=quantity,
        shipping_method=shipping[:20],
        shipping_region=shipping_region[:20],
        estimated_hours=estimated_hours if estimated_hours else round(internal["print_hours"], 2),
        volume_cm3=round(volume_cm3, 2),
        filament_grams=internal["filament_g"],
        printing_hours=internal["print_hours"],
        notes=notes[:2000] if notes else None,
        payment_method=payment_method[:20],
        subtotal=internal["filament_cost"] + internal["electricity_cost"] + internal["color_premium"],
        margin_pln=internal["margin_pln"],
        shipping_cost=calc["shipping_cost"],
        discount_pln=calc["discount_pln"],
        total=calc["total"],
        print_parts=calc["parts"],
        currency=calc["currency"],
        exchange_rate=calc["exchange_rate"],
        status="nowy",
        is_paid=False,
        created_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # —— bonus: +100 MB storage for paid orders >= 50 zł (K1.5 bonus quota) ——
    if order.total and order.total >= 50 and order.user_id:
        u = db.get(models.User, order.user_id)
        if u:
            u.bonus_mb = (u.bonus_mb or 0) + 100
            db.commit()

    # log discount usage
    if discount_code and db:
        db.execute(text("UPDATE discount_codes SET uses = uses + 1 WHERE code = :c"), {"c": discount_code.upper()})
        db.commit()

    return {
        "ok": True,
        "order_id": order.id,
        "total": calc["total"],
        "currency": calc["currency"],
        "exchange_rate": calc["exchange_rate"],
        "shipping_cost": calc["shipping_cost"],
        "product_subtotal": calc["product_subtotal"],
        "discount_pln": calc["discount_pln"],
    }


@router.get("/api/orders")
def list_orders(
    request: Request,
    status: str = None,
    country: str = None,
    material: str = None,
    paid: bool = None,
    search: str = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 50,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: list orders, sorted/filtered. search matches name/email/phone/address/city/notes; sort newest|oldest|total|date-paids."""
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, "Admin only")
    q = db.query(models.Order)
    if status:
        q = q.filter(models.Order.status == status)
    if paid is not None:
        q = q.filter(models.Order.is_paid == paid)
    if country:
        q = q.filter(models.Order.customer_country == country)
    if material:
        q = q.filter(models.Order.material == material)
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.filter(or_(
            models.Order.customer_name.ilike(like),
            models.Order.customer_email.ilike(like),
            models.Order.customer_phone.ilike(like),
            models.Order.customer_address.ilike(like),
            models.Order.customer_city.ilike(like),
            models.Order.customer_postal.ilike(like),
            models.Order.notes.ilike(like),
        ))
    if sort == "oldest":
        q = q.order_by(models.Order.id.asc())
    elif sort == "total":
        q = q.order_by(models.Order.total.desc())
    else:
        q = q.order_by(models.Order.id.desc())
    total_count = q.count()
    rows = []
    for o in q.offset((page - 1) * limit).limit(limit).all():
        rows.append({
            "id": o.id, "job_id": o.job_id, "job_uuid": o.job_uuid,
            "items": [{
                "id": it.id, "model_name": it.model_name, "job_uuid": it.job_uuid,
                "material": it.material, "color": it.color, "quantity": it.quantity,
                "volume_cm3": it.volume_cm3, "dims_mm": it.dims_mm,
                "filament_grams": it.filament_grams, "subtotal": it.subtotal,
                "margin_pln": it.margin_pln, "print_parts": it.print_parts,
            } for it in (o.items or [])],
            "customer_name": o.customer_name, "customer_email": o.customer_email,
            "customer_phone": o.customer_phone, "customer_city": o.customer_city,
            "customer_country": o.customer_country,
            "material": o.material, "color": o.color, "quantity": o.quantity,
            "shipping_method": o.shipping_method, "shipping_region": o.shipping_region,
            "filament_grams": o.filament_grams, "printing_hours": o.printing_hours,
            "volume_cm3": o.volume_cm3,
            "filament_cost": o.filament_cost, "electricity_cost": o.electricity_cost,
            "color_premium": o.color_premium, "subtotal": o.subtotal,
            "margin_pln": o.margin_pln,
            "shipping_cost": o.shipping_cost, "total": o.total,
            "currency": o.currency, "exchange_rate": o.exchange_rate,
            "discount_pln": o.discount_pln, "print_parts": o.print_parts,
            "status": o.status, "is_paid": o.is_paid, "payment_method": o.payment_method,
            "notes": o.notes, "admin_notes": getattr(o, "admin_notes", None),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return {"ok": True, "orders": rows, "total": total_count, "returned": len(rows), "page": page, "limit": limit}


@router.get("/api/orders/stats")
def order_stats(
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Dashboard stats — admin only."""
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, "Admin only")
    total = db.query(models.Order).count()
    paid_count = db.query(models.Order).filter(models.Order.is_paid == True).count()
    total_revenue = db.query(models.Order).filter(models.Order.is_paid == True).with_entities(
        models.Order.total).all()
    revenue = sum((r[0] or 0) for r in total_revenue)
    by_status = db.query(models.Order.status, func.count(models.Order.id)).group_by(models.Order.status).all()
    by_country = db.query(models.Order.customer_country, func.count(models.Order.id)).group_by(models.Order.customer_country).all()
    by_material = db.query(models.Order.material, func.count(models.Order.id)).group_by(models.Order.material).all()
    return {
        "ok": True, "stats": {
            "total_orders": total,
            "paid_orders": paid_count,
            "unpaid_orders": total - paid_count,
            "total_revenue_pln": round(revenue, 2),
            "by_status": [{"status": s, "count": c} for s, c in by_status],
            "by_country": [{"country": c, "count": n} for c, n in by_country],
            "by_material": [{"material": m, "count": n} for m, n in by_material],
        }
    }


# ── Powiadomienia email o zmianie statusu zamówienia ────────────────
_STATUS_MAIL = {
    "drukowane": ("Twój wydruk #%s jest w drukarce",
                  "Zaczęliśmy druk Twojego zamówienia #%s. Damy znać, gdy będzie gotowe."),
    "gotowe":    ("Wydruk #%s gotowy",
                  "Twoje zamówienie #%s jest wydrukowane i spakowane. %s"),
    "wysłane":   ("Wydruk #%s wysłany",
                  "Paczka z zamówieniem #%s jest w drodze. Jeśli to Paczkomat — kod odbioru wyśle InPost osobnym SMS/e-mailem."),
    "dostarczone": ("Dostarczone! Zamówienie #%s",
                  "Potwierdź proszę, że wszystko się zgadza — jeśli wydruk nie spełnia oczekiwań, napisz na hello@3dfile.link (druga próba lub zwrot)."),
    "anulowane": ("Zamówienie #%s anulowane",
                  "Zamówienie #%s zostało anulowane. Ewentualna wpłata wróci na konto płatności do 14 dni."),
}

def _notify_order_status(o, old_status: str, new_status: str):
    try:
        if not o or not o.customer_email or new_status == old_status:
            return
        tpl = _STATUS_MAIL.get(new_status)
        if not tpl:
            return
        subject, body = tpl[0] % o.id, tpl[1] % o.id
        if new_status == "gotowe":
            if getattr(o, "shipping_method", "") in ("pickup", "pickup_express"):
                body += " Odbiór osobisty: Gdańsk, ul. Międzygwiezdna 31/2 (Osowa) — odezwiemy się co do godziny."
            else:
                body += " Nadajemy najszybciej jak to możliwe."
        html = ("<div style='font-family:Inter,system-ui,sans-serif;max-width:520px;margin:0 auto;padding:24px;"
                "border:1px solid #e5e7eb;border-radius:12px'>"
                "<h2 style='margin:0 0 12px;color:#0B1730;font-size:18px'>3dfile.link</h2>"
                "<p style='color:#334155;line-height:1.6;font-size:14px'>" + body + "</p>"
                "<p style='color:#64748b;font-size:12px;margin-top:20px'>Pytania? hello@3dfile.link<br>3dfile.link — hosting i druk 3D</p></div>")
        from .mail import send_mail
        send_mail(o.customer_email, subject, html)
    except Exception as e:
        print(f"[order-notify] failed: {e}")


@router.patch("/api/orders/{order_id}")
def update_order(
    order_id: int,
    status: str = Form(None),
    is_paid: str = Form(None),
    shipping_method: str = Form(None),
    payment_method: str = Form(None),
    notes: str = Form(None),
    admin_notes: str = Form(None),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    o = db.get(models.Order, order_id)
    old_status = o.status
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    if status:
        valid = {"nowy", "wycena", "realizacja", "drukowane", "gotowe", "wysłane", "dostarczone", "anulowane"}
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        o.status = status
    if is_paid is not None:
        o.is_paid = is_paid.lower() in ("1", "true", "yes")
    if shipping_method:
        o.shipping_method = shipping_method[:20]
    if payment_method:
        o.payment_method = payment_method[:20]
    if notes is not None:
        o.notes = notes[:2000] if notes else None
    if admin_notes is not None:
        o.admin_notes = admin_notes[:2000] if admin_notes else None
    o.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(o)
    if status:
        _notify_order_status(o, old_status, status)
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": o.is_paid}





@router.get("/api/orders/{order_id}/export")
def export_order(order_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Pole", "Wartość"])
    w.writerow(["ID", o.id])
    w.writerow(["UUID modelu", o.job_uuid])
    w.writerow(["Data", o.created_at.isoformat()])
    w.writerow(["Klient", f"{o.customer_name} <{o.customer_email}>"])
    w.writerow(["Telefon", o.customer_phone or ""])
    w.writerow(["Adres", f"{o.customer_address or ''} {o.customer_city or ''} {o.customer_postal or ''} {o.customer_country}"])
    w.writerow(["Model", f"{o.material} / {o.color} / x{o.quantity}"])
    w.writerow(["Objętość (cm³)", o.volume_cm3 or 0])
    w.writerow(["Waga filamentu (g)", o.filament_grams or 0])
    w.writerow(["Czas druku (h)", o.printing_hours or 0])
    w.writerow(["Koszt filamentu", o.filament_cost or 0])
    w.writerow(["Koszt prądu", o.electricity_cost or 0])
    w.writerow(["Premium koloru", o.color_premium or 0])
    w.writerow(["Subtotal (fil+prąd+kolor)", o.subtotal or 0])
    w.writerow(["Marża (PLN)", o.margin_pln])
    w.writerow(["Wysyłka", f"{o.shipping_method} {o.shipping_region}: {o.shipping_cost} zł"])
    w.writerow(["Rabat", f"-{o.discount_pln} zł"])
    w.writerow(["Razem", f"{o.total} zł"])
    w.writerow(["Status", o.status])
    w.writerow(["Opłacone", "tak" if o.is_paid else "nie"])
    w.writerow(["Notatki admina", getattr(o, "admin_notes", None) or ""])
    resp = Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=zamowienie-{o.id}-{o.created_at.strftime('%Y%m%d')}.csv"
    return resp


@router.get("/api/orders/export")
def export_orders(admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Export all orders to Excel (admin only)."""
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    from openpyxl import Workbook
    from io import BytesIO
    wb = Workbook()
    ws = wb.active
    ws.title = "Zamówienia"
    ws.append(["ID", "Data", "Imię", "Email", "Telefon", "Adres", "Miasto", "Kraj",
               "Materiał", "Kolor", "Ilość", "Wysyłka", "Objętość cm³", "Filament g",
               "Czas (h)", "Koszt filamentu", "Koszt prądu", "Premium koloru", "Subtotal", "Marża (PLN)", "Wysyłka (zł)",
               "Rabat", "Razem", "Currency", "Status", "Zapłacony", "Notatki"])
    for o in db.query(models.Order).order_by(models.Order.id.desc()).all():
        ws.append([
            o.id, o.created_at.strftime("%Y-%m-%d %H:%M"),
            o.customer_name, o.customer_email, o.customer_phone,
            o.customer_address, o.customer_city, o.customer_country,
            o.material, o.color, o.quantity, o.shipping_method,
            o.volume_cm3, o.filament_grams, o.printing_hours,
            o.filament_cost or 0, o.electricity_cost or 0, o.color_premium or 0,
            o.subtotal, o.margin_pln, o.shipping_cost, o.discount_pln,
            o.total, o.currency, o.status, "Tak" if o.is_paid else "Nie", o.notes
        ])
    # Sheet2: wszystkie modele (itemy) w zamówieniach — co drukować, ile razy
    ws_m = wb.create_sheet("Modele")
    ws_m.append(["Zamówienie", "Data", "Klient", "Email", "Model", "Ilość (szt)", "Materiał", "Kolor", "Ile kolorów/Druk kol.", "Objętość cm³", "Wymiary", "Filament g", "Koszt filamentu", "Subtotal", "Marża", "Status", "Zapłacony"])
    for o in db.query(models.Order).order_by(models.Order.id.desc()).all():
        items = list(o.items or [])
        if items:
            for it in items:
                ws_m.append([o.id, o.created_at.strftime("%Y-%m-%d"), o.customer_name, o.customer_email,
                    it.model_name, it.quantity, it.material, it.color, "", it.volume_cm3 or "", it.dims_mm or "",
                    it.filament_grams, it.filament_cost, it.subtotal, it.margin_pln, o.status, "Tak" if o.is_paid else "Nie"])
        else:
            ws_m.append([o.id, o.created_at.strftime("%Y-%m-%d"), o.customer_name, o.customer_email,
                o.job_uuid or "—", o.quantity, o.material, o.color, "", o.volume_cm3 or "", "",
                o.filament_grams, o.filament_cost, o.subtotal, o.margin_pln, o.status, "Tak" if o.is_paid else "Nie"])

    ws2 = wb.create_sheet("Statystyki")
    total_orders = db.query(models.Order).count()
    paid = db.query(models.Order).filter(models.Order.is_paid == True).count()
    revenue = db.query(models.Order).filter(models.Order.is_paid == True).with_entities(models.Order.total).all()
    ws2.append(["Liczba zamówień", total_orders])
    ws2.append(["Zapłacone", paid])
    ws2.append(["Niezapłacone", total_orders - paid])
    ws2.append(["Przychód (PLN)", round(sum(r[0] or 0 for r in revenue), 2)])
    stats = db.query(models.Order.status, func.count(models.Order.id)).group_by(models.Order.status).all()
    for s, c in stats:
        ws2.append([f"Status {s}", c])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=zamowienia_3dfile_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"}
    )


# ── Admin pricing config ──

@router.get("/api/admin/pricing")
def get_pricing(db: Session = Depends(get_db), admin=Depends(require_admin)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    rows = {r.key: r for r in db.query(models.PricingConfig).all()}
    # Efektywny cennik: wartości z bazy nadpisały domyślne; pokazujemy JEDNĄ listę
    out = []
    def _emit(key, default, kind="float"):
        r = rows.get(key)
        out.append({"key": key, "value": (r.value if r else str(default)),
                    "kind": kind, "custom": bool(r),
                    "default": str(default),
                    "updated_at": r.updated_at.isoformat() if (r and r.updated_at) else None})
    _emit("margin_percent", MARGIN_PERCENT)
    _emit("kwh_pln", DEFAULT_KWH)
    _emit("watts", DEFAULT_WATTS)
    _emit("packing_pln", PACKING_FEE_PLN)
    _emit("free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)
    _emit("small_order_max_product_pln", SMALL_ORDER_MAX_PRODUCT)
    _emit("small_order_ship_flat_pln", SMALL_ORDER_SHIP_FLAT)
    _emit("max_part_area_mm2", MAX_PART_AREA_MM2)
    for mat, price in sorted(DEFAULT_MATERIAL_PRICES.items()):
        _emit(f"material:{mat}", price)
    for tier, regions in DEFAULT_SHIPPING.items():
        for region, val in regions.items():
            _emit(f"shipping_{tier}:{region}", val)
    # ręczne wpisy w bazie, których nie ma w domyślnych (np. color:*)
    for k, r in sorted(rows.items()):
        if k not in {o["key"] for o in out}:
            out.append({"key": k, "value": r.value, "kind": r.kind, "custom": True,
                        "default": "", "updated_at": r.updated_at.isoformat() if r.updated_at else None})
    return out


@router.post("/api/admin/pricing")
def set_pricing(
    key: str = Form(...),
    value: str = Form(...),
    kind: str = Form("float"),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    row = db.query(models.PricingConfig).filter(models.PricingConfig.key == key).first()
    if row:
        row.value = value
        row.kind = kind
        row.updated_at = datetime.utcnow()
    else:
        row = models.PricingConfig(key=key, value=value, kind=kind)
        db.add(row)
    db.commit()
    return {"ok": True, "key": key, "value": value}


@router.get("/api/admin/materials")
def get_materials(db: Session = Depends(get_db)):
    """List all material + color prices — public (for print.html pricing table)."""
    materials = {}
    for m in DEFAULT_MATERIAL_PRICES:
        materials[m] = {
            "price_kg": float(_cfg(db, f"material:{m}", DEFAULT_MATERIAL_PRICES.get(m, 110.0))),
            "density": DENSITIES.get(m, 1.24),
            "display": m,
            "desc": MATERIAL_DESCRIPTIONS.get(m, ""),
        }
    colors = {c: float(_cfg(db, f"color:{c}", DEFAULT_COLOR_PREMIUM.get(c, 0.0))) for c in DEFAULT_COLOR_PREMIUM}
    return {
        "materials": materials,
        "colors": colors,
        "density_map": {m: DENSITIES.get(m, 1.24) for m in DEFAULT_MATERIAL_PRICES},
        "shipping": {
            tier: {region: float(_cfg(db, f"shipping_{tier}:{region}", DEFAULT_SHIPPING[tier][region])) for region in DEFAULT_SHIPPING[tier]}
            for tier in DEFAULT_SHIPPING
        },
        "margin_percent": float(_cfg(db, "margin_percent", MARGIN_PERCENT)),
        "max_part_area_mm2": float(_cfg(db, "max_part_area_mm2", MAX_PART_AREA_MM2)),
    }


# ── Admin discount codes CRUD ──

@router.get("/api/admin/discount_codes")
def list_discount_codes(db: Session = Depends(get_db), admin=Depends(require_admin)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    rows = db.execute(text(
        "SELECT code, discount_pln, discount_pct, expires_at, is_active, uses, max_uses, min_order_pln FROM discount_codes ORDER BY code"
    )).fetchall()
    return [{"code": r[0], "discount_pln": r[1], "discount_pct": r[2],
             "expires_at": r[3].isoformat() if r[3] else None, "is_active": r[4],
             "uses": r[5], "max_uses": r[6], "min_order_pln": r[7] or 0} for r in rows]

@router.post("/api/admin/discount_codes")
def add_or_update_discount_code(
    code: str = Form(...),
    discount_pln: float = Form(0.0),
    discount_pct: float = Form(0.0),
    expires_at: str = Form(None),
    is_active: str = Form("1"),
    max_uses: int = Form(0),
    min_order_pln: float = Form(0.0),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    import datetime as _dt
    exp = None
    if expires_at:
        try:
            exp = _dt.datetime.fromisoformat(expires_at.replace("Z", ""))
        except ValueError:
            pass
    row = db.execute(text(
        "SELECT code FROM discount_codes WHERE code = :c"
    ), {"c": code.upper()}).fetchone()
    if row:
        db.execute(text("""UPDATE discount_codes SET discount_pln=:pln, discount_pct=:pct,
            expires_at=:exp, is_active=:act, max_uses=:mu, min_order_pln=:mop WHERE code=:c"""),
            {"c": code.upper(), "pln": discount_pln, "pct": discount_pct, "exp": exp,
             "act": is_active.lower() in ("1","true","yes"), "mu": max_uses, "mop": min_order_pln})
    else:
        db.execute(text("""INSERT INTO discount_codes
            (code, discount_pln, discount_pct, expires_at, is_active, uses, max_uses, min_order_pln)
            VALUES (:c, :pln, :pct, :exp, :act, 0, :mu, :mop)"""),
            {"c": code.upper(), "pln": discount_pln, "pct": discount_pct, "exp": exp,
             "act": is_active.lower() in ("1","true","yes"), "mu": max_uses, "mop": min_order_pln})
    db.commit()
    return {"ok": True, "code": code.upper()}

@router.delete("/api/admin/discount_codes/{code}")
def delete_discount_code(code: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    db.execute(text("DELETE FROM discount_codes WHERE code = :c"), {"c": code.upper()})
    db.commit()
    return {"ok": True}

# ---- Multi-model order: several uploaded models in one cart (1 shipping) ----
class OrderItemReq(BaseModel):
    job_id: Optional[int] = None
    job_uuid: Optional[str] = None
    model_name: Optional[str] = None
    material: str = "PLA"
    color: str = "natural"
    colors: int = 1
    quantity: int = 1
    volume_cm3: float = 0
    estimated_hours: float = 0
    dims: Optional[str] = None


class MultiOrderReq(BaseModel):
    name: str
    email: str
    phone: str = None
    address: str = None
    city: str = None
    postal_code: str = None
    country: str = "PL"
    shipping: str = "standard"
    shipping_region: str = "PL"
    discount_code: str = None
    notes: str = None
    payment_method: str = "blik"
    currency: str = "PLN"
    items: List[OrderItemReq]


@router.post("/api/orders/multi")
def create_multi_order(req: MultiOrderReq, db: Session = Depends(get_db)):
    """Create an order with multiple models. Each item priced via calculate_price,
    one shared shipping + packing. Returns order_id, item_count, totals."""
    try:
        return _create_multi_order_impl(req, db)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=f"multi order failed: {e}")


def _create_multi_order_impl(req: MultiOrderReq, db: Session = Depends(get_db)):
    if not req.items:
        raise HTTPException(400, detail="Brak modeli w zamówieniu")
    shipping_cost = round(_cfg_value(db, req.shipping, req.shipping_region), 2)
    packing_fee = 0.0 if req.shipping in ("pickup", "pickup_express") else float(_cfg(db, "packing_pln", PACKING_FEE_PLN))
    shipping_cost = round(shipping_cost + packing_fee, 2)

    total = shipping_cost
    subtotal_sum = 0.0
    margin_sum = 0.0
    discount_pln = 0.0
    items_rows = []
    for it in req.items:
        calc = calculate_price(
            material=it.material, color=it.color, quantity=it.quantity,
            shipping=req.shipping, shipping_region=req.shipping_region,
            volume_cm3=it.volume_cm3 or 0, estimated_hours=it.estimated_hours or 0,
            dims=it.dims, discount_code=req.discount_code, db=db, currency="PLN",
        )
        internal = calc["internal"]
        # Multi-color premium: 1 coloring = normal; each extra color +20 zł, next +10 zł ea.
        # (printed model with N colors is more expensive than single-color)
        n_colors = max(1, getattr(it, "colors", 1) or 1)
        color_mult = 0.0
        if n_colors > 1:
            color_mult = 20.0 + (n_colors - 2) * 10.0
        row = models.OrderItem(
            job_id=it.job_id, job_uuid=it.job_uuid,
            model_name=(it.model_name or it.job_uuid or "Model"),
            material=it.material[:30], color=it.color[:140], quantity=it.quantity,
            volume_cm3=round(it.volume_cm3 or 0, 2), dims_mm=it.dims,
            filament_grams=internal["filament_g"],
            filament_cost=internal["filament_cost"],
            electricity_cost=internal["electricity_cost"],
            color_premium=internal["color_premium"],
            subtotal=internal["filament_cost"] + internal["electricity_cost"] + internal["color_premium"],
            margin_pln=internal["margin_pln"],
            print_parts=internal["print_parts"],
        )
        subtotal_sum += row.subtotal + row.margin_pln + color_mult   # product (druk) + multi-color
        margin_sum += row.margin_pln
        if n_colors > 1:
            row.model_name = (row.model_name or "Model") + f" ({n_colors}x kolor)"
        total += (calc["total"] - calc["shipping_cost"]) + color_mult   # product per item (PLN, no shipping)
        items_rows.append(row)

    # MAŁE ZAMÓWIENIE: flat wysyłka (spójne z /api/calculate)
    product_pln = total - shipping_cost  # sama produkcja
    _new_ship = _apply_small_order_shipping(product_pln, shipping_cost, req.shipping)
    if _new_ship != shipping_cost:
        total = product_pln + _new_ship
        shipping_cost = _new_ship
    # FREE SHIPPING: product >= 200 PLN -> shipping gratis (Tom covers cost)
    if shipping_cost > 0 and req.shipping not in ("pickup", "pickup_express") and product_pln >= float(_cfg(db, "free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)):
        total -= shipping_cost
        shipping_cost = 0.0

    # discount across whole order (apply once on product total)
    if req.discount_code and db:
        d, info = _apply_discount(db, req.discount_code, max(subtotal_sum, 3.0))
        discount_pln = d
        total -= d

    if total < 3.0:
        total = subtotal_sum if subtotal_sum > 3.0 else 3.0
    total = _ceil05(total)

    cur = (req.currency or "PLN").upper()
    rate = {"USD": settings.currency_rate_usd, "EUR": settings.currency_rate_eur}.get(cur, 1.0)
    total_cur = _ceil05(total / rate if rate else total)

    order = models.Order(
        user_id=None,
        customer_name=req.name[:100], customer_email=req.email[:255],
        customer_phone=req.phone[:30] if req.phone else None,
        customer_address=req.address[:500] if req.address else None,
        customer_city=req.city[:100] if req.city else None,
        customer_postal=req.postal_code[:20] if req.postal_code else None,
        customer_country=req.country[:30],
        material="MIX", color="mixed",
        quantity=sum(i.quantity for i in req.items),
        shipping_method=req.shipping[:20], shipping_region=req.shipping_region[:20],
        estimated_hours=0.0, volume_cm3=round(sum(i.volume_cm3 or 0 for i in req.items), 2),
        filament_grams=round(sum(i.filament_grams for i in items_rows), 2),
        filament_cost=round(sum(i.filament_cost for i in items_rows), 2),
        electricity_cost=round(sum(i.electricity_cost for i in items_rows), 2),
        color_premium=round(sum(i.color_premium for i in items_rows), 2),
        printing_hours=0.0,
        notes=req.notes or None,
        payment_method=req.payment_method[:20],
        subtotal=round(subtotal_sum, 2),
        margin_pln=round(margin_sum, 2),
        shipping_cost=round(shipping_cost, 2),
        discount_pln=round(discount_pln, 2),
        total=round(total, 2),
        print_parts=sum(i.print_parts for i in items_rows),
        currency=cur,
        exchange_rate=rate,
        status="nowy", is_paid=False,
    )
    db.add(order)
    db.flush()
    for r in items_rows:
        r.order_id = order.id
        db.add(r)
    db.commit()

    if req.discount_code:
        try:
            db.execute(text("UPDATE discount_codes SET uses = uses + 1 WHERE code = :c"), {"c": req.discount_code.upper()})
            db.commit()
        except Exception:
            db.rollback()

    return {
        "ok": True, "order_id": order.id,
        "total": total_cur, "currency": cur, "exchange_rate": rate,
        "shipping_cost": _ceil05(shipping_cost / rate) if rate else shipping_cost,
        "item_count": len(items_rows),
        "discount_pln": round(discount_pln, 2),
    }


class SaveShippingReq(BaseModel):
    ship_full_name: str = None
    ship_phone: str = None
    ship_address: str = None
    ship_city: str = None
    ship_postal: str = None
    ship_country: str = "PL"


@router.put("/api/account/shipping")
def save_shipping(req: SaveShippingReq, db: Session = Depends(get_db),
                  user: models.User = Depends(require_user)):
    """Zapisz dane do wysyłki druku na profilu — auto-fill w kolejnych zamówieniach."""
    user.ship_full_name = (req.ship_full_name or "")[:100] or None
    user.ship_phone = (req.ship_phone or "")[:30] or None
    user.ship_address = (req.ship_address or "")[:500] or None
    user.ship_city = (req.ship_city or "")[:100] or None
    user.ship_postal = (req.ship_postal or "")[:20] or None
    user.ship_country = (req.ship_country or "PL")[:30]
    db.commit()
    return {"ok": True}

# —— Admin: usuń zamówienie (wraz z itemami) ——
@router.delete("/api/orders/{order_id}")
def delete_order(order_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Delete order + its items (admin)."""
    o = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Zamówienie nie istnieje")
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).delete(synchronize_session=False)
    db.delete(o)
    db.commit()
    return {"ok": True, "deleted": order_id}
