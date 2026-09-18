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
from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from . import models
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
    "TPU": 130.0, "TPU 75D": 150.0,
    "PA12 CF": 349.0, "PA12": 180.0,
    "PCTG": 140.0,
    "Iglidur I150PF": 450.0, "Iglidur I180PF": 480.0, "Iglidur I190PF": 520.0,
    "PLA Matte": 100.0, "PLA Silk": 110.0, "PLA Glow": 130.0,
    "BAMBU PLA Basic": 99.0, "BAMBU PETG HF": 129.0, "BAMBU ASA": 159.0,
    "BAMBU PA12-CF": 349.0, "BAMBU PLA Matte": 109.0,
}

DEFAULT_COLOR_PREMIUM = {
    "natural": 0.0, "black": 0.0, "white": 0.0,
    "blue": 5.0, "red": 5.0, "green": 5.0, "yellow": 5.0,
    "orange": 7.0, "purple": 7.0, "pink": 7.0,
    "gray": 3.0, "silver": 10.0, "gold": 15.0,
    "carbon": 20.0, "wood": 15.0, "brass": 25.0,
}

DEFAULT_SHIPPING = {
    "standard":  {"PL": 15.0, "EU": 35.0, "GLOBAL": 55.0},
    "express":   {"PL": 25.0, "EU": 55.0, "GLOBAL": 85.0},
    "priority":  {"PL": 40.0, "EU": 80.0, "GLOBAL": 130.0},
    "pickup":    {"PL": 0.0,  "EU": 0.0, "GLOBAL": 0.0},
}

DEFAULT_WATTS = 150
DEFAULT_KWH = getattr(settings, "kwh_price", 1.50)  # Bamboo P1S ~1.5 zł/kWh
MARGIN_PERCENT = getattr(settings, "print_margin_percent", 68)
MAX_PART_AREA_MM2 = 65536  # 256×256 mm build (Bamboo P1S)
DENSITIES = {
    "PLA": 1.24, "PLA HT": 1.24, "PLA CF": 1.24,
    "PLA Matte": 1.24, "PLA Silk": 1.24, "PLA Glow": 1.24,
    "PETG": 1.27, "PETG HF": 1.27, "PETG FR": 1.28,
    "BAMBU PLA Basic": 1.24, "BAMBU PETG HF": 1.27, "BAMBU ASA": 1.07,
    "BAMBU PA12-CF": 1.25, "BAMBU PLA Matte": 1.24,
    "ABS": 1.04, "ASA": 1.07, "ASA CF": 1.15,
    "TPU": 1.20, "TPU 75D": 1.20,
    "PA12": 1.14, "PA12 CF": 1.25,
    "PCTG": 1.27,
    "Iglidur I150PF": 1.42,
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
    "TPU 75D": "TPU twardy (twardość 75D), na pograniczu twardego plastiku i gumy. Sprężyste części, zawiasy klipsowe, elementy wymagające elastyczności i wytrzymałości.",
    "PA12 CF": "Najmocniejszy: nylon z włóknem węglowym. Elementy funkcjonalne pod obciążeniem, części mechaniczne, koła zębate, haki, wsporniki. Najwyższa wytrzymałość i odporność na ścieranie.",
    "PA12": "Nylon — mocny, odporny na ścieranie i chemię. Koła zębate, elementy mechaniczne, części pracujące, łożyska ślizgowe.",
    "PCTG": "Bardzo przezroczysty, odporny na uderzenia, do kontaktu z żywnością. Elementy optyczne, przezroczyste obudowy, pojemniki.",
    "Iglidur I150PF": "Łożyskowy Iglidur — samosmarujący, cichy i odporny na ścieranie. Łożyska ślizgowe, prowadnice, zawiasy, części ruchome pracujące bez smarowania.",
    "Iglidur I180PF": "Iglidur o podwyższonej wytrzymałości mechanicznej. Łożyska i części ruchome o większym obciążeniu.",
    "Iglidur I190PF": "Iglidur najwyższej wytrzymałości — do wymagających zastosowań technicznych, łożysk i elementów obciążonych.",
    "BAMBU PLA Basic": "PLA Bambu Lab — uniwersalny, do prototypów, modeli i codziennych części.",
    "BAMBU PETG HF": "PETG Bambu Lab o wysokiej jakości, przejrzysty i udarny.",
    "BAMBU ASA": "ASA Bambu Lab — odporny na UV, do elementów zewnętrznych i motoryzacyjnych.",
    "BAMBU PA12-CF": "Nylon z włóknem węglowym Bambu Lab — najwyższa wytrzymałość do części funkcjonalnych.",
    "BAMBU PLA Matte": "Matowy PLA Bambu Lab — estetyczne wykończenie do modeli i dekoracji.",
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
    discount_pln = 0.0
    discount_info = None
    if discount_code and db:
        discount_pln, discount_info = _apply_discount(db, discount_code, product_total)

    # minimum order: product must be >= 5 zł
    if product_total < 5.0:
        product_total = 5.0
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
        color=color[:20],
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
    limit: int = 100,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: list all orders sorted desc by id."""
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
    return {"ok": True, "orders": rows, "total": len(rows)}


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
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": o.is_paid}


@router.get("/api/orders/{order_id}/pay")
def get_payment_info(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Return BLIK payment info (static — real BLIK dynamic via API)."""
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "ok": True,
        "order_id": o.id,
        "total": o.total,
        "currency": o.currency or "PLN",
        "exchange_rate": o.exchange_rate or 1.0,
        "blik_code": "123456789",  # static — replace with real BLIK dynamic
        "bank_name": "mBank",
        "titled": f"3dfile.link #{o.id}",
    }


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
    w.writerow(["Notatki admina", o.admin_notes or ""])
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
    rows = db.query(models.PricingConfig).all()
    return [{"key": r.key, "value": r.value, "kind": r.kind, "updated_at": r.updated_at.isoformat() if r.updated_at else None} for r in rows]


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
