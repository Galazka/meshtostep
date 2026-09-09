"""Remove entire credit system from MeshToStep codebase.
Edits CRLF files via Python text replacement."""
import os

BASE = r"C:\Users\galaz\Desktop\MeshToStep"

def read(p):
    with open(os.path.join(BASE, p), encoding="utf-8") as f:
        return f.read()

def write(p, content):
    with open(os.path.join(BASE, p), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)

def patch(p, old, new):
    c = read(p)
    assert old in c, f"MISSING in {p}:\n{old[:80]}"
    write(p, c.replace(old, new, 1))
    print(f"  patched {p}")

# ── 1. models.py ─────────────────────────────────────────────────────
print("=== models.py ===")
# Remove User.credits column
patch("backend/app/models.py",
    '    credits = Column(Integer, default=3, nullable=False)\n', '')

# Remove User.credit_adjustments relationship
patch("backend/app/models.py",
    '    credit_adjustments = relationship("CreditAdjustment", back_populates="user", foreign_keys="CreditAdjustment.user_id")\n', '')

# Remove Job.credits_used
patch("backend/app/models.py",
    '    credits_used = Column(Integer, default=0)\n', '')

# Remove CreditPack class
patch("backend/app/models.py",
    '''\nclass CreditPack(Base):
    __tablename__ = "credit_packs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    credits = Column(Integer, nullable=False)
    price_usd = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


''', '')

# Remove Payment.credits_granted and pack_id, pack relationship
patch("backend/app/models.py",
    '    pack_id = Column(Integer, ForeignKey("credit_packs.id"), nullable=True)\n', '')
patch("backend/app/models.py",
    '    credits_granted = Column(Integer, default=0)\n', '')
patch("backend/app/models.py",
    '    pack = relationship("CreditPack")\n', '')

# Remove CreditAdjustment class
patch("backend/app/models.py",
    '''

class CreditAdjustment(Base):
    __tablename__ = "credit_adjustments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    credits_before = Column(Integer, nullable=False)
    credits_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="credit_adjustments", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_id])
''', '')

# ── 2. config.py ─────────────────────────────────────────────────────
print("=== config.py ===")
patch("backend/app/config.py", '    FREE_CREDITS: int = 3\n', '')

# ── 3. routes_payments.py ────────────────────────────────────────────
print("=== routes_payments.py ===")
write("backend/app/routes_payments.py", '''"""Stripe webhook placeholder — credit system removed. — 3dfile.link"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db

router = APIRouter(prefix="/api", tags=["payments"])


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook — currently a no-op placeholder."""
    return {"ok": True}
''')

# ── 4. routes_admin.py ───────────────────────────────────────────────
print("=== routes_admin.py ===")
c = read("backend/app/routes_admin.py")

# Remove credits_sold from stats
c = c.replace(
    '    credits_sold = db.query(func.sum(models.Payment.credits_granted)).scalar() or 0\n'
    '    revenue_usd = db.query(func.sum(models.Payment.amount_usd)).filter(\n',
    '    revenue_usd = db.query(func.sum(models.Payment.amount_usd)).filter(\n'
)
c = c.replace('        "credits_sold": credits_sold,\n', '')
c = c.replace('        "credits_used": total_jobs,\n', '')

# Remove credits from user list response
c = c.replace('            "credits": u.credits,\n', '')

# Remove credit adjustments query and credits from user detail
c = c.replace(
    '    # Credit adjustments\n    adjustments = (\n        db.query(models.CreditAdjustment)\n        .filter(models.CreditAdjustment.user_id == user_id)\n        .order_by(desc(models.CreditAdjustment.created_at))\n        .limit(20)\n        .all()\n    )\n\n',
    ''
)
c = c.replace('        "credits": user.credits,\n', '')
c = c.replace(
    '        "adjustments": [{\n            "id": a.id, "amount": a.amount, "reason": a.reason,\n            "credits_before": a.credits_before, "credits_after": a.credits_after,\n            "admin_id": a.admin_id, "created_at": str(a.created_at),\n        } for a in adjustments],\n',
    ''
)

# Remove credits_granted from payments display
c = c.replace('            "id": p.id, "amount_usd": p.amount_usd, "credits_granted": p.credits_granted,\n',
              '            "id": p.id, "amount_usd": p.amount_usd,\n')

# Remove entire credit adjustment endpoint + req model
c = c.replace(
    '''# ── Credit adjustment ───────────────────────────────────────────────
class CreditAdjustReq(BaseModel):
    amount: int  # positive = grant, negative = revoke
    reason: str = ""


@router.post("/users/{user_id}/credits")
def adjust_credits(
    user_id: int,
    body: CreditAdjustReq,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually adjust a user's credits with full audit trail."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if body.amount == 0:
        raise HTTPException(400, "Amount cannot be zero")

    credits_before = user.credits
    user.credits = max(0, user.credits + body.amount)

    adjustment = models.CreditAdjustment(
        user_id=user_id,
        admin_id=admin.id,
        amount=body.amount,
        reason=body.reason or None,
        credits_before=credits_before,
        credits_after=user.credits,
    )
    db.add(adjustment)
    db.commit()

    return {
        "ok": True,
        "credits": user.credits,
        "adjustment_id": adjustment.id,
    }


''', '')

write("backend/app/routes_admin.py", c)

# ── 5. routes_auth.py ────────────────────────────────────────────────
print("=== routes_auth.py ===")
c = read("backend/app/routes_auth.py")

# Remove credits=settings.FREE_CREDITS from register
c = c.replace('        credits=settings.FREE_CREDITS,\n', '')

# Remove credits from register response
c = c.replace('            "credits": user.credits,\n', '')

write("backend/app/routes_auth.py", c)

# ── 6. routes_convert.py ─────────────────────────────────────────────
print("=== routes_convert.py ===")
patch("backend/app/routes_convert.py", '        job.credits_used = 0\n', '')

# ── 7. database.py ───────────────────────────────────────────────────
print("=== database.py ===")
c = read("backend/app/database.py")

# Remove CreditPack seeding
c = c.replace(
    '        if db.query(models.CreditPack).count() == 0:\n'
    '            db.add_all([models.CreditPack(name="Start 5", credits=5, price_usd=0.99),models.CreditPack(name="Pack 25", credits=25, price_usd=2.99),models.CreditPack(name="Pack 100", credits=100, price_usd=7.99)])\n'
    '            db.commit()\n',
    ''
)

# Remove credits from admin bootstrap
c = c.replace(
    '                admin = models.User(email=settings.ADMIN_EMAIL.lower().strip(), password_hash=hash_password(settings.ADMIN_PASSWORD), credits=999999, is_admin=True, email_verified=True)\n',
    '                admin = models.User(email=settings.ADMIN_EMAIL.lower().strip(), password_hash=hash_password(settings.ADMIN_PASSWORD), is_admin=True, email_verified=True)\n'
)

write("backend/app/database.py", c)

print("\n=== All backend patches done ===")
