# K4 — User Accounts

## Goal: Minimal anon-optional auth. Orders przepisane na `user_id` (nullable).

## Files
- backend/app/models.py — dodaj `User` (id, email, password_hash, is_admin, created_at) + `Order.user_id` FK
- backend/app/auth.py (nowy) — /register, /login, /me, JWT (PyJWT stdlib-friendly)
- backend/app/main.py — `/api/auth`, `/api/me` z `Depends(get_current_user)`
- backend/app/routes_print.py — `POST /api/orders` z opcjonalnym `user_id`

## DB
```sql
CREATE TABLE users (id INTEGER PK, email TEXT UNIQUE, password_hash TEXT, is_admin INTEGER DEFAULT 0, created_at TEXT);
ALTER TABLE orders ADD COLUMN user_id INTEGER REFERENCES users(id);
```

## Endpoints
| Method | Path | Auth | Desc |
|--------|------|------|------|
| POST | /api/auth/register | none | {email, password} → {token} |
| POST | /api/auth/login | none | {email, password} → {token} |
| GET | /api/me | bearer | user info |
| POST | /api/orders | optional | creates order, user_id=token user or NULL |

## Test command
`pytest tests/test_auth.py -v` (test_register_login_anon_order, test_order_tied_to_user)

## Deploy
`railway up --service meshtostep`
