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
from datetime import datetime, timezone
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
# Ceny szpuli 1 kg (brutto PLN) — realny rynek PL wrzesien 2026, marki Bambu Lab / Extrudr:
#   PLA Basic ~66-92 (refill/szpula) · PETG ~65-90 · ABS ~71-99 · ASA Bambu ~119-149
#   PLA-CF ~149-199 · TPU ~119-149 · Silk/Matte ~99-129 · Glow ~129-149
DEFAULT_MATERIAL_PRICES = {
    "PLA": 82.0, "PLA HT": 109.0, "PLA CF": 175.0,
    "PETG": 86.0, "PETG HF": 115.0, "PETG FR": 145.0,
    "ABS": 85.0, "ASA": 139.0, "ASA CF": 259.0,
    "TPU": 129.0,
    "PLA Matte": 99.0, "PLA Silk": 115.0, "PLA Glow": 135.0,
}

# DOPŁATA KLIENCKA za szczególne pigmenty (srebrny/złoty/węglowy/przezroczysty).
# UWAGA: to NIE jest koszt Toma — filament w różnych kolorach kosztuje go tyle samo,
# więc dopłata jest czystym przychodem (doliczana do ceny, nie mnożona marżą).
DEFAULT_COLOR_PREMIUM = {
    "natural": 0.0, "black": 0.0, "white": 0.0,
    "blue": 0.0, "red": 0.0, "green": 0.0, "yellow": 0.0,
    "orange": 0.0, "purple": 0.0, "pink": 0.0, "gray": 0.0,
    "silver": 20.0, "gold": 25.0, "carbon": 15.0, "wood": 15.0,
    "transparent": 30.0, "brass": 25.0,
}

# DOPŁATA za wydruk wielokolorowy (jako jeden model): 1. kolor ekstra +20 zł, każdy kolejny +10 zł.
MULTICOLOR_FIRST_EXTRA_PLN = 20.0
MULTICOLOR_NEXT_EXTRA_PLN = 10.0


def multicolor_fee(n_colors: int) -> float:
    """Dopłata kliencka za N kolorów w jednym wydruku (N=1 → 0)."""
    n = max(1, int(n_colors or 1))
    if n <= 1:
        return 0.0
    return MULTICOLOR_FIRST_EXTRA_PLN + (n - 2) * MULTICOLOR_NEXT_EXTRA_PLN

# WYPEŁNIENIE (infill) — bazowa cena druku = 15% (standard farmy).
# Model masy: V_materialu(f) = (s + f*(1-s))*V_objetosci — s = udzial powlok
# i sklepien (obrysy + gore/dol), niezalezny od infill. Normalizacja do bazy 15%
# (cena podstawowa sie NIE zmienia). 10%~0.93, 25%~1.14, 50%~1.51, 100%~2.23x.
INFILL_MIN_DEFAULT = 10
INFILL_MAX_DEFAULT = 100
INFILL_BASE_DEFAULT = 15
INFILL_SHELL_SHARE_DEFAULT = 0.35


# InPost 2026: Paczkomat gabaryt A 16,49 zł.
# Standard = 5 dni (normalna cena).
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
PACKING_FEE_PLN = 3.0  # karton + etykieta + folia na przesyłkę (InPost Paczkomat), stałe niezależnie od liczby produktów
PICKUP_EXPRESS_FEE_PLN = 19.00  # odbiór osobisty ekspres: priorytet w kolejce, gotowe do 2 dni roboczych (opłata all-inclusive)
FREE_SHIPPING_MIN_PLN = 200.0  # zamówienia >=200 zł → wysyłka gratis (Tom pokrywa koszt)
MIN_PRINT_PLN = 10.0  # minimalna cena samego wydruku (hero/order mówią "od 10 zł")

# ── Małe zamówienia: promocyjna wysyłka (Tom dopłaca różnicę z marży — konkurencyjny pricing) ──
SMALL_ORDER_MAX_PRODUCT = 40.0   # poniżej tej kwoty PRODUKTU obowiązuje flat
SMALL_ORDER_SHIP_FLAT = 9.90     # wysyłka+pakowanie ŁĄCZNIE (normalnie InPost 16.49 + packing 3.00 = 19.49)

def _apply_small_order_shipping(product_pln: float, shipping_cost: float, shipping: str, db=None) -> float:
    """Małe zamówienia (< progu produktu, nie pickup): wysyłka+pakowanie flat.
    Bez tego mały model 6 cm³ kosztowałby 26 zł (wysyłka zjada 80% ceny).
    Próg i kwota flat czytane z bazy (klucze small_order_max_product_pln / small_order_ship_flat_pln)."""
    max_prod = float(_cfg(db, "small_order_max_product_pln", SMALL_ORDER_MAX_PRODUCT))
    flat = float(_cfg(db, "small_order_ship_flat_pln", SMALL_ORDER_SHIP_FLAT))
    if shipping_cost > 0 and shipping not in ("pickup", "pickup_express") and product_pln < max_prod:
        return min(shipping_cost, flat)
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


THROUGHPUTS = {"PLA": 280, "PLA HT": 200, "PLA CF": 220, "PLA Matte": 260, "PLA Silk": 260, "PLA Glow": 260,
               "PETG": 240, "PETG HF": 260, "PETG FR": 220, "PCTG": 200, "ASA": 220, "ASA CF": 200,
               "ABS": 250, "TPU": 150}


def estimate_print_time_hours(volume_cm3: float, material: str = "PLA", parts: int = 1, db=None) -> float:
    """mm³/s throughput per material — konfigurowalne w DB: klucz throughput:{MATERIAL}."""
    if not volume_cm3 or volume_cm3 <= 0:
        return 2.0
    mm3 = volume_cm3 * 1000  # całkowita objętość modelu (parts drukowane równolegle)
    throughput = float(_cfg(db, f"throughput:{material}", THROUGHPUTS.get(material, 200)))
    base = max(0.25, mm3 / (throughput * 3600))
    # fixed per-model setup overhead (not per-part) — Bamboo P1S auto-leveling ~2min
    return base + 0.1


def estimate_filament_grams(volume_cm3: float, material: str = "PLA", db=None) -> float:
    """Density in g/cm³ — konfigurowalna w DB: klucz density:{MATERIAL}."""
    density = float(_cfg(db, f"density:{material}", DENSITIES.get(material, 1.24)))
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



def _infill_cfg(db=None):
    return {
        "min": int(float(_cfg(db, "infill_min", INFILL_MIN_DEFAULT))),
        "max": int(float(_cfg(db, "infill_max", INFILL_MAX_DEFAULT))),
        "base": int(float(_cfg(db, "infill_default", INFILL_BASE_DEFAULT))),
        "shell": float(_cfg(db, "infill_shell_share", INFILL_SHELL_SHARE_DEFAULT)),
    }


def _infill_factor(infill, db=None) -> float:
    """Mnożnik kosztu (materiał+prąd+czas) wzgl. bazowego wypełnienia (15% = 1.00).
    10% ≈ 0.93, 25% ≈ 1.14, 50% ≈ 1.51, 75% ≈ 1.86, 100% ≈ 2.23."""
    c = _infill_cfg(db)
    try:
        f = float(infill if infill not in (None, "") else c["base"])
    except (TypeError, ValueError):
        f = float(c["base"])
    f = min(max(f / 100.0, c["min"] / 100.0), c["max"] / 100.0)
    base = min(max(c["base"] / 100.0, 0.05), 1.0)
    sh = min(max(c["shell"], 0.05), 0.95)
    return round((sh + f * (1.0 - sh)) / (sh + base * (1.0 - sh)), 4)



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
    colors: int = 1,
    infill: int = None,
):
    """Calculate price. Returns dict with PUBLIC (customer-facing) + INTERNAL cost sheet.

    Public: shipping_cost, total (= product_subtotal + shipping - discount)
    Internal: filament_cost, electricity_cost (KOSZT), color_premium + multicolor_fee
              (DOPŁATA KLIENCKA = przychód, nie koszt), margin_percent, margin_pln,
              profit_pln, discount_pln, parts

    Kolejność (jedno źródło prawdy — order.html liczy identycznie):
      koszt = filament + prąd
      baza  = max(min_print, koszt + marża)
      produkt = baza + dopłata za pigment + dopłata za wielokolor
      total = _ceil05(produkt + wysyłka - rabat)
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
    filament_g_per = estimate_filament_grams(vol_per_part, material, db)
    total_filament_g = filament_g_per * parts * quantity
    filament_cost = (total_filament_g / 1000) * mat_price_kg

    hours = max(estimated_hours, estimate_print_time_hours(volume_cm3, material, parts, db)) if volume_cm3 else max(estimated_hours, 2.0)
    power_cost = (watts / 1000) * hours * kwh
    # KOSZT (to, co realnie płaci Tom): filament + prąd. Kolor NIE jest kosztem —
    # filament w każdym kolorze kosztuje tyle samo, więc dopłata za pigment/wielokolor
    # jest czystym przychodem i NIE jest mnożona marżą.
    # WYPEŁNIENIE: materiał + prąd + czas skalowane fakorem (15% = 1.00, bez zmian cen)
    infill_pct = int(infill) if infill not in (None, "") else _infill_cfg(db)["base"]
    inf_factor = _infill_factor(infill_pct, db)
    filament_cost = filament_cost * inf_factor
    power_cost = power_cost * inf_factor
    total_filament_g = total_filament_g * inf_factor
    hours = hours * inf_factor
    cost_pln = filament_cost + power_cost
    color_premium = float(_cfg(db, f"color:{color}", DEFAULT_COLOR_PREMIUM.get(color, 0.0))) * quantity
    multi_fee = multicolor_fee(colors)
    surcharge_pln = round(color_premium + multi_fee, 2)

    subtotal = round(cost_pln, 2)
    margin_pln = round(cost_pln * (margin_pct / 100), 2)
    product_base = round(cost_pln + margin_pln, 2)  # baza klienta: koszt + marża

    # MINIMUM ZAMÓWIENIA (druk): baza zawsze >= min_print_pln (hero/order mówią "od 10 zł")
    min_print = float(_cfg(db, "min_print_pln", MIN_PRINT_PLN))
    if product_base < min_print:
        product_base = min_print

    # co klient płaci za DRUK = baza + dopłaty (pigment, wielokolor)
    product_total = round(product_base + surcharge_pln, 2)

    shipping_cost = round(_cfg_value(db, shipping, shipping_region), 2)
    # Packing fee (karton, etykieta, folia) — dodawany tylko gdy paczka jest wysyłana,
    # NIE przy odbiorze osobistym. Konfigurowalne: packing_pln (default 5.00).
    packing_fee = 0.0 if shipping in ("pickup", "pickup_express") else float(_cfg(db, "packing_pln", PACKING_FEE_PLN))
    shipping_cost = round(shipping_cost + packing_fee, 2)
    discount_pln = 0.0
    discount_info = None
    if discount_code and db:
        discount_pln, discount_info = _apply_discount(db, discount_code, product_total)

    # MAŁE ZAMÓWIENIE: flat wysyłka (zanim free-shipping check)
    so_max = float(_cfg(db, "small_order_max_product_pln", SMALL_ORDER_MAX_PRODUCT))
    so_flat = float(_cfg(db, "small_order_ship_flat_pln", SMALL_ORDER_SHIP_FLAT))
    small_order = shipping_cost > 0 and product_total < so_max and shipping not in ("pickup", "pickup_express")
    if small_order:
        shipping_cost = min(shipping_cost, so_flat)
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
        "product_subtotal": subtotal_cur,   # druk + marża + dopłaty (ukryta struktura)
        "product_subtotal_pln": product_total,
        "surcharge_pln": surcharge_pln,     # dopłata za pigment + wielokolor (jawna linia)
        "color_premium_pln": round(color_premium, 2),
        "multicolor_fee_pln": round(multi_fee, 2),
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
            "cost_pln": round(cost_pln, 2),          # realny koszt Toma (filament + prąd)
            "color_premium": round(color_premium, 2),  # DOPŁATA KLIENCKA (przychód!)
            "multicolor_fee": round(multi_fee, 2),     # DOPŁATA KLIENCKA (przychód!)
            "colors": int(colors or 1),
            "margin_percent": margin_pct,
            "margin_pln": margin_pln,                  # marża 68% od kosztu
            "profit_pln": round(product_total - cost_pln, 2),  # marża + dopłaty
            "infill_percent": infill_pct,
            "infill_factor": inf_factor,
            "print_parts": parts,
            "print_hours": round(hours, 2),
            "material_price_kg": mat_price_kg,
            "discount_info": discount_info,
        },
        "parts": parts,
        "infill": infill_pct,
        "infill_factor": inf_factor,
        "infill_cfg": _infill_cfg(db),
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
    colors: int = Form(1, ge=1),
    infill: int = Form(None),
    db: Session = Depends(get_db),
):
    """Public price calculator — only shows shipping + total to customer."""
    calc = calculate_price(material, color, quantity, shipping, shipping_region,
                           volume_cm3, estimated_hours, dims, discount_code, db, currency,
                           colors, infill=infill)
    return {
        "ok": True,
        "product_subtotal": calc["product_subtotal"],
        "shipping_cost": calc["shipping_cost"],
        "free_shipping": calc["free_shipping"],
        "small_order_shipping": calc["small_order_shipping"],
        "discount_pln": calc["discount_pln"],
        "surcharge_pln": calc["surcharge_pln"],
        "color_premium_pln": calc["color_premium_pln"],
        "multicolor_fee_pln": calc["multicolor_fee_pln"],
        "filament_grams": (calc.get("internal") or {}).get("filament_g"),
        "printing_hours": (calc.get("internal") or {}).get("print_hours"),
        "min_print_pln": float(_cfg(db, "min_print_pln", MIN_PRINT_PLN)),
        "at_min_print": float(calc.get("product_subtotal_pln") or 0) <= float(_cfg(db, "min_print_pln", MIN_PRINT_PLN)) + 0.01,
        "total": calc["total"],
        "currency": calc["currency"],
        "exchange_rate": calc["exchange_rate"],
        "parts": calc["parts"],
        "product_subtotal_pln": calc["product_subtotal_pln"],
        "shipping_cost_pln": calc["shipping_cost_pln"],
        "infill": calc["infill"],
        "infill_factor": calc["infill_factor"],
        "infill_cfg": calc["infill_cfg"],
        "material": material,
        "color": color,
        "colors": colors,
        "quantity": quantity,
        "print_hours": calc["internal"]["print_hours"],
    }


@router.get("/api/pricing/public")
def public_pricing(db: Session = Depends(get_db)):
    """Parametry cennika widoczne dla klienta (order.html liczy te same liczby co backend).

    Bez tego order.html miał ZASZYTE na sztywno 16.49/3/9.90/40/200 — zmiana w /admin/pricing
    nie wpływała na stronę zamówienia (rozjazd ceny pokazywanej vs pobieranej).
    """
    tiers = {}
    for ship in ("standard", "express", "pickup", "pickup_express"):
        tiers[ship] = {}
        for reg in ("PL", "EU", "GLOBAL"):
            tiers[ship][reg] = float(_cfg_value(db, ship, reg))
    return {
        "ok": True,
        "currency": "PLN",
        "rates": {"PLN": 1.0, "EUR": float(settings.currency_rate_eur or 4.3), "USD": float(settings.currency_rate_usd or 4.0)},
        "shipping_tiers": tiers,
        "packing_pln": float(_cfg(db, "packing_pln", PACKING_FEE_PLN)),
        "pickup_express_fee_pln": PICKUP_EXPRESS_FEE_PLN,
        "small_order_max_product_pln": float(_cfg(db, "small_order_max_product_pln", SMALL_ORDER_MAX_PRODUCT)),
        "small_order_ship_flat_pln": float(_cfg(db, "small_order_ship_flat_pln", SMALL_ORDER_SHIP_FLAT)),
        "free_shipping_min_pln": float(_cfg(db, "free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)),
        "min_print_pln": float(_cfg(db, "min_print_pln", MIN_PRINT_PLN)),
        # Dopłaty za pigment (jawna linia w koszyku) + wielokolor. Frontend MUSI użyć tych
        # samych liczb, inaczej pokaże inną cenę niż backend policzy.
        "color_surcharge": {
            k: float(_cfg(db, f"color:{k}", v)) for k, v in DEFAULT_COLOR_PREMIUM.items()
        },
        "materials": {m: {"price_kg": float(_cfg(db, f"material:{m}", DEFAULT_MATERIAL_PRICES.get(m, 110.0))),
                           "density": DENSITIES.get(m, 1.24)} for m in DEFAULT_MATERIAL_PRICES},
        "infill": _infill_cfg(db),
        "margin_percent": float(_cfg(db, "margin_percent", MARGIN_PERCENT)),
        "min_print_pln": float(_cfg(db, "min_print_pln", MIN_PRINT_PLN)),
        "watts": float(_cfg(db, "watts", DEFAULT_WATTS)),
        "kwh_pln": float(_cfg(db, "kwh_pln", DEFAULT_KWH)),
        "multicolor_first_extra_pln": float(_cfg(db, "multicolor_first_extra_pln", MULTICOLOR_FIRST_EXTRA_PLN)),
        "multicolor_next_extra_pln": float(_cfg(db, "multicolor_next_extra_pln", MULTICOLOR_NEXT_EXTRA_PLN)),
    }


@router.get("/api/config/infill")
def get_infill_config(db: Session = Depends(get_db)):
    """Public: widełki wypełnienia dla konfiguratora (order.html)."""
    return {"ok": True, **_infill_cfg(db)}


@router.post("/api/discount/validate")
def validate_discount(
    code: str = Form(...),
    amount: float = Form(0),
    db: Session = Depends(get_db),
):
    """Sprawdza kod rabatowy PRZED złożeniem zamówienia (order.html: przycisk 'Zastosuj')."""
    code = (code or "").strip().upper()
    if not code:
        return {"ok": False, "valid": False, "message": "Podaj kod"}
    value = max(float(amount or 0), float(_cfg(db, "min_print_pln", MIN_PRINT_PLN)))
    d, info = _apply_discount(db, code, value)
    if d <= 0:
        return {"ok": True, "valid": False, "code": code, "discount_pln": 0.0, "message": "Kod nieaktywny, wygasł lub nie spełnia warunków"}
    return {"ok": True, "valid": True, "code": code, "discount_pln": round(d, 2), "info": info, "message": "Kod zastosowany: -" + f"{d:.2f}".rstrip("0").rstrip(".") + " zł"}


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

    _notify_created(order)

    # —— bonus: +500 MB storage for paid orders >= 50 zł (K1.5 bonus quota) ——
    if order.total and order.total >= 50 and order.user_id:
        u = db.get(models.User, order.user_id)
        if u:
            u.bonus_mb = (u.bonus_mb or 0) + 500
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
                "surcharge_pln": getattr(it, "surcharge_pln", 0.0) or 0.0,
                "infill": getattr(it, "infill", 15) or 15,
                "colors": max(1, len(str(it.color or "").split(" + "))),
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
            "surcharge_pln": getattr(o, "surcharge_pln", 0.0) or 0.0,
            "multicolor_fee": getattr(o, "multicolor_fee", 0.0) or 0.0,
            "cost_pln": getattr(o, "cost_pln", 0.0) or 0.0,
            "profit_pln": round(((o.total or 0.0) - (o.shipping_cost or 0.0)) - (getattr(o, "cost_pln", 0.0) or 0.0), 2),
            "shipping_cost": o.shipping_cost, "total": o.total,
            "currency": o.currency, "exchange_rate": o.exchange_rate,
            "discount_pln": o.discount_pln, "print_parts": o.print_parts,
            "status": o.status, "is_paid": o.is_paid, "payment_method": o.payment_method,
            "notes": o.notes, "admin_notes": getattr(o, "admin_notes", None),
            "created_at": _iso(o.created_at),
            "tracking_code": getattr(o, "tracking_code", None),
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
def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None

def _warsaw(dt):
    if not dt:
        return None
    try:
        from zoneinfo import ZoneInfo
        return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Warsaw'))
    except Exception:
        pass
    import datetime as _d
    def _last_sun(y, mo, d0):
        d = _d.date(y, mo, d0)
        while d.weekday() != 6:
            d -= _d.timedelta(days=1)
        return d
    dst = _last_sun(dt.year, 3, 31) <= dt.date() < _last_sun(dt.year, 10, 31)
    return dt + _d.timedelta(hours=2 if dst else 1)

def _tracking_url(code):
    if not code:
        return None
    c = code.strip()
    if c.startswith('http'):
        return c
    if c.replace(' ', '').isdigit():
        return 'https://inpost.pl/sledzenie/' + c.replace(' ', '')
    return None

_FLOW = ["nowy", "wycena", "realizacja", "drukowane", "gotowe", "wysłane", "dostarczone"]
_FLOW_LBL = {"nowy": "Nowe", "wycena": "Wycena", "realizacja": "Realizacja", "drukowane": "Druk", "gotowe": "Gotowe", "wysłane": "Wysłane", "dostarczone": "Dostarczone"}

def _order_mail_html(o, subject_line, body_line, status=None, tracking=None):
    """Markowy szablon maila statusowego (table-HTML, inline CSS)."""
    import html as _h
    esc = _h.escape
    rows = ""
    try:
        for it in (o.items or [])[:6]:
            q = (" \u00d7" + str(it.quantity)) if (it.quantity or 1) > 1 else ""
            rows += ("<tr><td style='padding:6px 0;color:#334155;font-size:14px'>" + esc(it.model_name or "Model") +
                     "</td><td style='padding:6px 0;color:#64748b;font-size:13px;text-align:right'>" +
                     esc((it.material or "") + ((" / " + it.color) if it.color else "")) + q + "</td></tr>")
    except Exception:
        pass
    tl = ""
    if status and status in _FLOW:
        ci = _FLOW.index(status)
        cells = ""
        for i, k in enumerate(_FLOW):
            col = "#10b981" if i <= ci else "#e5e7eb"
            wt = ";font-weight:700" if i == ci else ""
            txt = "#0B1730" if i == ci else "#94a3b8"
            cells += ("<td style='text-align:center;padding:2px'><div style='height:8px;width:8px;border-radius:50%;margin:0 auto;background:" + col + "'></div>"
                      "<div style='font-size:9px;color:" + txt + wt + ";margin-top:4px'>" + _FLOW_LBL[k] + "</div></td>")
        tl = "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin:14px 0'><tr>" + cells + "</tr></table>"
    track = ""
    if tracking:
        tu = _tracking_url(tracking)
        track = ("<div style='background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:12px 16px;margin:14px 0'>"
                 "<span style='color:#0369a1;font-size:13px'>Śledzenie przesyłki:</span> <b style='color:#0B1730;font-size:14px'>" + esc(tracking) + "</b>"
                 + ("&nbsp;&nbsp;<a href='" + tu + "' style='color:#1d4ed8;font-weight:600;font-size:13px'>Track paczkę \u2192</a>" if tu else "") + "</div>")
    pay = ("<span style='background:#10b981;color:#fff;font-size:12px;padding:3px 10px;border-radius:999px'>\u2713 Opłacone</span>"
           if o.is_paid else
           "<span style='background:#fef3c7;color:#92400e;font-size:12px;padding:3px 10px;border-radius:999px'>Oczekuje na płatność</span>")
    return ("<div style='background:#f1f5f9;padding:28px 12px;font-family:Inter,Arial,sans-serif'>"
            "<div style='max-width:540px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden'>"
            "<div style='background:#0B1730;padding:18px 24px'><span style='color:#fff;font-weight:800;font-size:16px;letter-spacing:.4px'>3DFILE<span style='color:#2B5CE6'>.LINK</span></span>"
            "<span style='float:right;color:#94a3b8;font-size:12px'>Zamówienie #" + str(o.id) + "</span></div>"
            "<div style='padding:22px 24px'>"
            "<h2 style='margin:0 0 6px;color:#0B1730;font-size:19px'>" + subject_line + "</h2>" + tl +
            "<p style='color:#334155;line-height:1.65;font-size:14px;margin:10px 0'>" + body_line + "</p>" + track +
            "<table role='presentation' width='100%' style='border-top:1px solid #eef2f7;margin-top:10px'>" + rows + "</table>"
            "<div style='margin-top:12px;padding-top:12px;border-top:1px solid #eef2f7'>"
            "<table role='presentation' width='100%'><tr><td><b style='color:#0B1730;font-size:16px'>" + (("%.2f" % (o.total or 0)) + " " + esc(o.currency or "PLN")) + "</b></td>"
            "<td style='text-align:right'>" + pay + "</td></tr></table></div>"
            "<div style='margin-top:18px'><a href='https://3dfile.link/konto' style='display:inline-block;background:#2B5CE6;color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:11px 22px;border-radius:8px'>Moje zamówienia \u2192</a></div>"
            "</div>"
            "<div style='margin:16px 0 0;padding:13px 16px;background:#eef3ff;border:1px solid #dbe4ff;border-radius:10px'><b style='color:#0B1730;font-size:13.5px'>Nie masz jeszcze konta na 3dfile.link?</b><p style='margin:5px 0 7px;color:#334155;font-size:13px;line-height:1.6'>Załóż je na ten sam e‑mail — całą historię wydruków, statusy i rachunki zobaczysz w jednym miejscu, a na start dorzucamy <b>+500 MB</b> na pliki.</p><a href='https://3dfile.link/#register' style='color:#1d4ed8;font-weight:700;font-size:13px;text-decoration:none'>Załóż konto za darmo →</a></div>"
            "<div style='background:#f8fafc;border-top:1px solid #eef2f7;padding:14px 24px;color:#64748b;font-size:12px;line-height:1.7'>"
            "hello@3dfile.link \u00b7 tomgal@3dfile.link \u00b7 tel. +48 790 824 762<br>3dfile.link \u2014 hosting i druk 3D \u00b7 ul. Międzygwiezdna 31/2, 80-299 Gdańsk Osowa</div>"
            "</div></div>")

_STATUS_MAIL = {
    "wycena":      ("Wycena zamówienia #%s w toku",
                  "Przygotowujemy wycenę Twojego zamówienia #%s. Dostaniesz maila, gdy będzie gotowa."),
    "realizacja":  ("Zamówienie #%s przyjęte do realizacji",
                  "Zamówienie #%s jest w kolejce druku. Będziemy meldować każdy etap."),
    "drukowane": ("Twój wydruk #%s jest w drukarce",
                  "Zaczęliśmy druk Twojego zamówienia #%s. Damy znać, gdy będzie gotowe."),
    "gotowe":    ("Wydruk #%s gotowy",
                  "Twoje zamówienie #%s jest wydrukowane i spakowane. %s"),
    "wysłane":   ("Wydruk #%s wysłany — śledź paczkę",
                  "Paczka z zamówieniem #%s jest w drodze. Jeśli to Paczkomat — kod odbioru wyśle InPost osobnym SMS/e-mailem."),
    "dostarczone": ("Dostarczone! Zamówienie #%s",
                  "Potwierdź proszę, że wszystko się zgadza — jeśli wydruk nie spełnia oczekiwań, napisz na hello@3dfile.link (druga próba lub zwrot)."),
    "anulowane": ("Zamówienie #%s anulowane",
                  "Zamówienie #%s zostało anulowane. Ewentualna wpłata wróci na konto płatności do 14 dni."),
}

def _notify_created(o):
    """Mail potwierdzajacy przyjecie zamowienia (niezaleznie od platnosci)."""
    try:
        if not o or not o.customer_email:
            return
        pay_line = ("Płatność zaksięgowana — zamówienie wchodzi do kolejki druku." if o.is_paid
                    else "Płatność: <b>oczekuje</b> — dokończ ją w linku wyslanym przy zamówieniu lub na Twoim profilu. Po zaksięgowaniu status sam się zmieni, a Ty dostaniesz osobny e-mail.")
        html = _order_mail_html(o, "Zamówienie przyjęte", pay_line, status=o.status, tracking=getattr(o, "tracking_code", None))
        from .mail import send_mail
        send_mail(o.customer_email, f"Zamówienie #{o.id} przyjęte — 3dfile.link", html)
    except Exception as e:
        print(f"[order-notify] created failed: {e}")


def _notify_paid(o):
    try:
        extra = " Rachunek: <a href='https://3dfile.link/api/orders/%s/receipt'>pobierz online</a>%s" % (
            o.id, " · <a href='" + o.stripe_receipt_url + "'>potwierdzenie Stripe</a>" if getattr(o, "stripe_receipt_url", None) else "")
        html = _order_mail_html(
            o, "Płatność przyjęta \u2705",
            "Dziękujemy! Zamówienie <b>#%s</b> na kwotę <b>%.2f %s</b> jest opłacone i weszło do kolejki druku. Powiadomimy Cię o każdej zmianie statusu.%s" % (o.id, (o.total or 0), (o.currency or "PLN"), extra),
            status=o.status, tracking=getattr(o, "tracking_code", None))
        from .mail import send_mail
        send_mail(o.customer_email, f"Zamówienie #{o.id} opłacone — 3dfile.link", html)
    except Exception as e:
        print(f"[order-notify] paid failed: {e}")

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
        trk = getattr(o, "tracking_code", None)
        html = _order_mail_html(o, subject.split(" — ")[0], body, status=new_status, tracking=trk)
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

    tracking_code: str = Form(None),

    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    old_status = o.status
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
    if tracking_code is not None:
        o.tracking_code = tracking_code[:120].strip() or None
    was_unpaid = not o.is_paid
    o.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(o)
    if was_unpaid and o.is_paid:
        _notify_paid(o)
    if status:
        _notify_order_status(o, old_status, status)
    return {"ok": True, "order_id": o.id, "status": o.status, "is_paid": o.is_paid, "tracking_code": o.tracking_code}





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
    w.writerow(["Data", _warsaw(o.created_at).strftime("%Y-%m-%d %H:%M") if o.created_at else ""])
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
    w.writerow(["Dopłata wielokolor", getattr(o, "multicolor_fee", 0.0) or 0])
    w.writerow(["Dopłaty razem (pigment+multi)", getattr(o, "surcharge_pln", 0.0) or 0])
    w.writerow(["Subtotal (fil+prąd)", o.subtotal or 0])
    w.writerow(["Marża (PLN)", o.margin_pln])
    w.writerow(["Koszt całkowity (fil+prąd+pakowanie)", getattr(o, "cost_pln", 0.0) or 0])
    w.writerow(["Zysk (produkt bez wysyłki - koszt)", round(((o.total or 0.0) - (o.shipping_cost or 0.0)) - (getattr(o, "cost_pln", 0.0) or 0.0), 2)])
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
               "Czas (h)", "Koszt filamentu", "Koszt prądu", "Premium koloru", "Subtotal (fil+prąd)", "Marża (PLN)", "Wysyłka (zł)",
               "Rabat", "Razem", "Currency", "Status", "Zapłacony", "Wielokolor (dopłata)", "Dopłaty razem",
               "Koszt całkowity (+pakowanie)", "Zysk (produkt - koszt)", "Notatki"])
    for o in db.query(models.Order).order_by(models.Order.id.desc()).all():
        ws.append([
            o.id, (_warsaw(o.created_at).strftime("%Y-%m-%d %H:%M") if o.created_at else ""),

            o.customer_name, o.customer_email, o.customer_phone,
            o.customer_address, o.customer_city, o.customer_country,
            o.material, o.color, o.quantity, o.shipping_method,
            o.volume_cm3, o.filament_grams, o.printing_hours,
            o.filament_cost or 0, o.electricity_cost or 0, o.color_premium or 0,
            o.subtotal, o.margin_pln, o.shipping_cost, o.discount_pln,
            o.total, o.currency, o.status, "Tak" if o.is_paid else "Nie",
            getattr(o, "multicolor_fee", 0.0) or 0,
            getattr(o, "surcharge_pln", 0.0) or 0,
            getattr(o, "cost_pln", 0.0) or 0,
            round(((o.total or 0.0) - (o.shipping_cost or 0.0)) - (getattr(o, "cost_pln", 0.0) or 0.0), 2),
            o.notes
        ])
    # Sheet2: wszystkie modele (itemy) w zamówieniach — co drukować, ile razy
    ws_m = wb.create_sheet("Modele")
    ws_m.append(["Zamówienie", "Data", "Klient", "Email", "Model", "Ilość (szt)", "Materiał", "Kolor", "Ile kolorów/Druk kol.", "Objętość cm³", "Wypełnienie %", "Wymiary", "Filament g", "Koszt filamentu", "Subtotal", "Marża", "Status", "Zapłacony"])
    for o in db.query(models.Order).order_by(models.Order.id.desc()).all():
        items = list(o.items or [])
        if items:
            for it in items:
                ws_m.append([o.id, (_warsaw(o.created_at).strftime("%Y-%m-%d %H:%M") if o.created_at else ""), o.customer_name, o.customer_email,
                    it.model_name, it.quantity, it.material, it.color,
                    max(1, len(str(it.color or "").split(" + "))), it.volume_cm3 or "", getattr(it, "infill", 15) or 15, it.dims_mm or "",
                    it.filament_grams, it.filament_cost, it.subtotal, it.margin_pln, o.status, "Tak" if o.is_paid else "Nie"])
        else:
            ws_m.append([o.id, o.created_at.strftime("%Y-%m-%d"), o.customer_name, o.customer_email,
                o.job_uuid or "—", o.quantity, o.material, o.color, "", o.volume_cm3 or "", 15, "",
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
    # Etykiety/opis dla panelu admina — bez tego admin widzi surowe klucze ("dane z tabeli niejasne")
    def _meta(key):
        if key.startswith("material:"):
            return ("Cena szpuli — " + key.split(":", 1)[1], "Cena filamentu u dostawcy", "zł/kg", "Materiały")
        if key.startswith("density:"):
            return ("Gęstość — " + key.split(":", 1)[1], "Do przeliczenia cm³ na gramy", "g/cm³", "Materiały")
        if key.startswith("throughput:"):
            return ("Przepustowość — " + key.split(":", 1)[1], "Ile mm³ drukuje na sekundę", "mm³/s", "Materiały")
        if key.startswith("color:"):
            return ("Dopłata za kolor — " + key.split(":", 1)[1], "Premium za dodatkowy kolor", "zł", "Kolory")
        if key.startswith("shipping_"):
            t = key.split(":", 1)[0]
            reg = key.split(":", 1)[1] if ":" in key else ""
            return ("Wysyłka " + t.replace("shipping_", "") + " — " + reg, "Koszt samej wysyłki", "zł", "Wysyłka")
        return {
            "margin_percent": ("Marża", "Narzut doliczany do kosztu (cena = koszt × (1+marża/100))", "%", "Marża i prąd"),
            "kwh_pln": ("Cena prądu", "Koszt energii do wyliczenia prądu wydruku", "zł/kWh", "Marża i prąd"),
            "watts": ("Pobór mocy drukarki", "Watts pobierane przez drukarkę", "W", "Marża i prąd"),
            "packing_pln": ("Pakowanie", "Karton + folia + etykieta (tylko przy wysyłce)", "zł", "Wysyłka"),
            "free_shipping_min_pln": ("Darmowa wysyłka od", "Powyżej tej kwoty produktu wysyłka gratis", "zł", "Wysyłka"),
            "small_order_max_product_pln": ("Małe zamówienie do", "Poniżej tej kwoty produktu obowiązuje flat wysyłki", "zł", "Wysyłka"),
            "small_order_ship_flat_pln": ("Flat wysyłki (małe)", "Wysyłka+pakowanie łącznie dla małych zamówień", "zł", "Wysyłka"),
            "max_part_area_mm2": ("Max pole wydruku", "Limit stołu Bambu P1S", "mm²", "Limity"),
            "min_print_pln": ("Minimum druku", "Minimalna cena samego wydruku", "zł", "Limity"),
            "infill_default": ("Wypełnienie bazowe", "Procent wypełnienia wkalkulowany w cenę podstawową", "%", "Wypełnienie"),
            "infill_min": ("Wypełnienie min.", "Najniższe wypełnienie w konfiguratorze", "%", "Wypełnienie"),
            "infill_max": ("Wypełnienie maks.", "Najwyższe wypełnienie — elementy konstrukcyjne", "%", "Wypełnienie"),
            "infill_shell_share": ("Udział powłok", "Część objętości przypadająca na obrysy+sklepienia (kalibracja krzywej ceny)", "0–1", "Wypełnienie"),
        }.get(key, (key, "", "", "Inne"))

    def _emit(key, default, kind="float"):
        r = rows.get(key)
        lbl, desc, unit, group = _meta(key)
        out.append({"key": key, "value": (r.value if r else str(default)),
                    "kind": kind, "custom": bool(r),
                    "default": str(default),
                    "label": lbl, "desc": desc, "unit": unit, "group": group,
                    "updated_at": r.updated_at.isoformat() if (r and r.updated_at) else None})
    _emit("margin_percent", MARGIN_PERCENT)
    _emit("kwh_pln", DEFAULT_KWH)
    _emit("watts", DEFAULT_WATTS)
    _emit("packing_pln", PACKING_FEE_PLN)
    _emit("free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)
    _emit("small_order_max_product_pln", SMALL_ORDER_MAX_PRODUCT)
    _emit("small_order_ship_flat_pln", SMALL_ORDER_SHIP_FLAT)
    _emit("max_part_area_mm2", MAX_PART_AREA_MM2)
    _emit("min_print_pln", MIN_PRINT_PLN)
    _emit("infill_default", INFILL_BASE_DEFAULT)
    _emit("infill_min", INFILL_MIN_DEFAULT)
    _emit("infill_max", INFILL_MAX_DEFAULT)
    _emit("infill_shell_share", INFILL_SHELL_SHARE_DEFAULT)
    for mat, price in sorted(DEFAULT_MATERIAL_PRICES.items()):
        _emit(f"material:{mat}", price)
    for mat, dens in sorted(DENSITIES.items()):
        _emit(f"density:{mat}", dens)
    for mat, th in sorted(THROUGHPUTS.items()):
        _emit(f"throughput:{mat}", th)
    for col, prem in sorted(DEFAULT_COLOR_PREMIUM.items()):
        _emit(f"color:{col}", prem)
    for tier, regions in DEFAULT_SHIPPING.items():
        for region, val in regions.items():
            _emit(f"shipping_{tier}:{region}", val)
    # ręczne wpisy w bazie, których nie ma w domyślnych (np. color:*)
    for k, r in sorted(rows.items()):
        if k not in {o["key"] for o in out}:
            lbl, desc, unit, group = _meta(k)
            out.append({"key": k, "value": r.value, "kind": r.kind, "custom": True,
                        "default": "", "label": lbl, "desc": desc, "unit": unit, "group": group,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None})
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
    infill: int = 15


class MultiOrderReq(BaseModel):
    name: str
    email: str
    phone: str = None
    address: str = None
    city: str = None
    postal_code: str = None
    country: str = "PL"

    dry_run: bool = False

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
    subtotal_sum = 0.0   # KOSZT: filament + prąd
    margin_sum = 0.0
    surcharge_sum = 0.0  # dopłata pigment
    multicolor_sum = 0.0  # dopłata wielokolor
    discount_pln = 0.0
    items_rows = []
    for it in req.items:
        n_colors = max(1, getattr(it, "colors", 1) or 1)
        calc = calculate_price(
            material=it.material, color=it.color, quantity=it.quantity,
            shipping=req.shipping, shipping_region=req.shipping_region,
            volume_cm3=it.volume_cm3 or 0, estimated_hours=it.estimated_hours or 0,
            dims=it.dims, discount_code=req.discount_code, db=db, currency="PLN",
            colors=n_colors, infill=int(it.infill or 15),
        )
        internal = calc["internal"]
        # Dopłaty (pigment + wielokolor) liczy SILNIK — jedno źródło prawdy, zero duplikacji.
        row_surcharge = round(calc.get("color_premium_pln", 0.0), 2)
        row_multi = round(calc.get("multicolor_fee_pln", 0.0), 2)
        row = models.OrderItem(
            job_id=it.job_id, job_uuid=it.job_uuid,
            model_name=(it.model_name or it.job_uuid or "Model"),
            material=it.material[:30], color=it.color[:140], quantity=it.quantity,
            volume_cm3=round(it.volume_cm3 or 0, 2), dims_mm=it.dims,
            filament_grams=internal["filament_g"],
            filament_cost=internal["filament_cost"],
            electricity_cost=internal["electricity_cost"],
            color_premium=internal["color_premium"],
            subtotal=round(internal["filament_cost"] + internal["electricity_cost"], 2),
            surcharge_pln=row_surcharge,
            margin_pln=internal["margin_pln"],
            print_parts=internal["print_parts"],
            infill=int(internal.get("infill_percent") or 15),
        )
        subtotal_sum += row.subtotal
        margin_sum += row.margin_pln
        surcharge_sum += row_surcharge
        multicolor_sum += row_multi
        if n_colors > 1:
            row.model_name = (row.model_name or "Model") + f" ({n_colors}x kolor)"
        total += calc["product_subtotal_pln"]   # produkt per item (PLN, bez wysyłki)
        items_rows.append(row)

    # MAŁE ZAMÓWIENIE: flat wysyłka (spójne z /api/calculate)
    product_pln = total - shipping_cost  # sama produkcja
    _new_ship = _apply_small_order_shipping(product_pln, shipping_cost, req.shipping, db)
    if _new_ship != shipping_cost:
        total = product_pln + _new_ship
        shipping_cost = _new_ship
    # FREE SHIPPING: product >= próg -> shipping gratis (Tom covers cost)
    if shipping_cost > 0 and req.shipping not in ("pickup", "pickup_express") and product_pln >= float(_cfg(db, "free_shipping_min_pln", FREE_SHIPPING_MIN_PLN)):
        total -= shipping_cost
        shipping_cost = 0.0

    # discount across whole order (apply once on product total)
    _min_print = float(_cfg(db, "min_print_pln", MIN_PRINT_PLN))
    if req.discount_code and db:
        d, info = _apply_discount(db, req.discount_code, max(product_pln, _min_print))
        discount_pln = d
        total -= d

    if total < _min_print:
        total = max(product_pln + shipping_cost, _min_print)
    total = _ceil05(total)

    cur = (req.currency or "PLN").upper()
    rate = {"USD": settings.currency_rate_usd, "EUR": settings.currency_rate_eur}.get(cur, 1.0)
    total_cur = _ceil05(total / rate if rate else total)

    if req.dry_run:
        # WYCENA — dokładnie te same liczby co tworzenie zamówienia, bez zapisu.
        return {
            "ok": True, "dry_run": True,
            "total": total_cur, "currency": cur, "exchange_rate": rate,
            "shipping_cost": round(shipping_cost, 2),
            "discount_pln": round(discount_pln, 2),
            "product_total_pln": round(product_pln, 2),
            "item_count": len(req.items),
            "items": [{"model_name": (r.model_name or "")[:60], "product_pln": round(r.subtotal - r.margin_pln, 2), "infill": r.infill} for r in items_rows],
        }


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
        surcharge_pln=round(surcharge_sum, 2),
        multicolor_fee=round(multicolor_sum, 2),
        cost_pln=round(subtotal_sum + packing_fee, 2),
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

    _notify_created(order)
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
@router.get("/api/account/orders")
def account_orders(user=Depends(require_user), db: Session = Depends(get_db)):
    """Historia zamówień zalogowanego użytkownika: po user_id LUB po zweryfikowanym emailu
    (zamówienia składane przed założeniem konta / jako gość)."""
    from sqlalchemy import or_
    if not user:
        raise HTTPException(401, detail="Zaloguj się")
    q = (db.query(models.Order)
         .filter(or_(models.Order.user_id == user.id,
                     models.Order.customer_email == user.email))
         .order_by(models.Order.id.desc()).limit(100))
    out = []
    for o in q.all():
        out.append({"id": o.id, "created_at": _iso(o.created_at),
                    "status": o.status, "is_paid": bool(o.is_paid),
                    "tracking_code": getattr(o, "tracking_code", None),
                    "tracking_url": _tracking_url(getattr(o, "tracking_code", None)),
                    "total": o.total, "currency": o.currency or "PLN",
                    "shipping_method": o.shipping_method,
                    "items": [{"model_name": it.model_name, "material": it.material, "color": it.color,
                               "quantity": it.quantity, "volume_cm3": it.volume_cm3} for it in (o.items or [])],
                    "receipt_url": f"/api/orders/{o.id}/receipt",
                    "stripe_receipt": o.stripe_receipt_url if getattr(o, "stripe_receipt_url", None) else None})
    return {"ok": True, "orders": out}


@router.get("/api/orders/{order_id}/receipt")
def order_receipt(order_id: int, request: Request, token: str = None, db: Session = Depends(get_db)):
    """Rachunek (HTML, przyjazny do druku/PDF). Właściciel (user_id lub email) albo admin."""
    from .auth import _decode_token
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(404, detail="Order not found")
    me = None
    auth = request.headers.get("authorization", "")
    raw = auth[7:] if auth.startswith("Bearer ") else (token or request.query_params.get("token") or "")
    if raw:
        me = _decode_token(raw)
    if not me:
        raise HTTPException(401, detail="Zaloguj się aby pobrać rachunek")
    if not getattr(me, "is_admin", False) and o.user_id != me.id and (o.customer_email or "").lower() != (me.email or "").lower():
        raise HTTPException(403, detail="To nie Twoje zamówienie")
    items = list(o.items or [])
    if not items and o.job_uuid:
        items = [SimpleNamespace(model_name=o.material or "Model", material=o.material, color=o.color,
                                 quantity=o.quantity or 1, volume_cm3=o.volume_cm3, subtotal=None, margin_pln=None)]
    rows = "".join(f"<tr><td>{getattr(it,'model_name','')}</td><td>{getattr(it,'material','') or ''}</td>"
                   f"<td>{getattr(it,'color','') or ''}</td><td style='text-align:center'>{getattr(it,'quantity',1)}</td></tr>" for it in items)
    ship_txt = {"pickup": "odbiór osobisty (Gdańsk, ul. Międzygwiezdna 31/2)",
                "pickup_express": "odbiór osobisty — EKSPRES",
                "standard": "InPost Paczkomat (standard)", "express": "InPost (ekspres)",
                "address": "kurier pod adres"}.get(o.shipping_method or "", o.shipping_method or "")
    html = f"""<!doctype html><html lang=pl><head><meta charset=utf-8><title>Rachunek #{o.id} — 3dfile.link</title>
<style>body{{font-family:Inter,system-ui,sans-serif;color:#0f172a;max-width:640px;margin:32px auto;padding:0 20px}}
h1{{font-size:20px;border-bottom:2px solid #0B1730;padding-bottom:8px}}table{{width:100%;border-collapse:collapse;margin:14px 0}}
td,th{{padding:6px 8px;border-bottom:1px solid #e2e8f0;font-size:14px;text-align:left}}.sum{{font-size:15px}}
.tot{{font-weight:700;font-size:17px;border-top:2px solid #0B1730}}.muted{{color:#64748b;font-size:12px}}
@media print{{.noprint{{display:none}}}}</style></head><body>
<h1>RACHUNEK nr {o.id}/{o.created_at.strftime('%Y') if o.created_at else ''}</h1>
<p><b>Sprzedawca:</b> 3dfile.link (sprzedaż okazjonalna) · Gdańsk · hello@3dfile.link<br>
<b>Data wystawienia:</b> {_warsaw(o.created_at).strftime('%Y-%m-%d %H:%M') if o.created_at else ''}<br>
<b>Nabywca:</b> {o.customer_name or ''} · {o.customer_email or ''}{(' · ' + o.customer_phone) if o.customer_phone else ''}<br>
{('<b>Adres:</b> ' + (o.customer_address or '') + ', ' + (o.customer_city or '')) if o.customer_address else '<b>Odbiór:</b> osobisty / wg wyboru'}</p>
<table><tr><th>Model</th><th>Materiał</th><th>Kolor</th><th>Ilość</th></tr>{rows}</table>
<table class=sum>
<tr><td>Wysyłka / dostawa</td><td style=text-align:right>{ship_txt}</td></tr>
<tr><td>Koszt wysyłki i pakowania</td><td style=text-align:right>{(o.shipping_cost or 0):.2f} {o.currency or 'PLN'}</td></tr>
{(f"<tr><td>Rabat</td><td style=text-align:right>-{(o.discount_pln or 0):.2f} {o.currency or 'PLN'}</td></tr>") if (o.discount_pln or 0) else ''}
<tr class=tot><td>RAZEM</td><td style=text-align:right>{(o.total or 0):.2f} {o.currency or 'PLN'}</td></tr></table>
<p class=muted>Płatność: {('opłacona (' + (o.payment_method or '—') + ')') if o.is_paid else 'oczekuje na płatność'} · kwota ostateczna.
Status zamówienia: <b>{o.status}</b></p>
{('<p><a href="' + o.stripe_receipt_url + '">🧾 Potwierdzenie płatności Stripe</a></p>') if getattr(o, 'stripe_receipt_url', None) else ''}
<p class=muted>Dokument nie jest fakturą VAT w rozumieniu przepisów — sprzedaż okazjonalna osoby fizycznej.
Dla firm: dane NIP w zamówieniu: {('NIP w uwagach' if (o.notes and 'NIP' in (o.notes or '')) else 'brak')}.</p>
<div class=noprint><a href=/zamow>← Nowe zamówienie</a> · <button onclick=print()>Drukuj / zapisz PDF</button></div>
</body></html>"""
    return HTMLResponse(html)


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
