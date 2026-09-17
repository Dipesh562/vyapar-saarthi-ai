# ARCHITECTURE.md — System Architecture & Component Design

---

## 1. End-to-End System Architecture

```
+---------------------------------------------------------------------------------------+
|                                  USER INTERFACE                                       |
|              (Web Browser POS / Mobile PWA / Counter Microphone Audio)                |
+---------------------------------------------------------------------------------------+
                                           |
                                    HTTP REST / JSON
                                           v
+---------------------------------------------------------------------------------------+
|                         FLASK APPLICATION FACTORY (app/__init__.py)                   |
|                                                                                       |
|  Security & Auth Layer:                                                               |
|   ├── Flask-Login (@login_required)         — Session-based authentication           |
|   ├── werkzeug.security                     — Scrypt password hashing                |
|   ├── HTTP-Only Lax session cookies         — XSS & CSRF protection                  |
|   └── @require_role('owner')                — Role-based route access control        |
|                                                                                       |
|  Blueprint API Routing Layer (15 Blueprints):                                         |
|  +-----------------------+---------------------------+------------------------------+ |
|  | Blueprint             | URL Prefix                | Purpose                      | |
|  +-----------------------+---------------------------+------------------------------+ |
|  | main_bp               | / (root)                  | HTML index, /manifest.json,  | |
|  |                       |                           | /sw.js (PWA service worker)  | |
|  | auth_bp               | /api/v1/auth              | Register owner/helper, login | |
|  | voice_bp              | /api/v1/voice             | STT transcribe, voice bill,  | |
|  |                       |                           | merchant feedback learning   | |
|  | billing_bp            | /api/v1/billing           | Create/confirm/void drafts   | |
|  | products_bp           | /api/v1/products          | Catalog CRUD & search        | |
|  | inventory_bp          | /api/v1/inventory         | Stock levels, adjust, history| |
|  | inventory_csv_bp      | /api/v1/inventory/csv     | CSV bulk import & export     | |
|  | customers_bp          | /api/v1/customers         | Customer profiles & Khata    | |
|  | payments_bp           | /api/v1/payments          | Idempotent Udhaar payment    | |
|  | receipts_bp           | /api/v1/receipts          | Invoice generation           | |
|  | sales_bp              | /api/v1/sales             | Sales reporting & analytics  | |
|  | alerts_bp             | /api/v1/alerts            | Low stock notifications      | |
|  | ai_bp                 | /api/v1/ai                | Direct AI assistant queries  | |
|  | assistant_bp          | /api/v1/assistant         | Conversation assistant       | |
|  | health_bp             | /health                   | System healthcheck           | |
|  +-----------------------+---------------------------+------------------------------+ |
|                                                                                       |
|  Decoupled Domain Services Layer (app/services/):                                     |
|   ├── STTClient                  — Audio-to-text transcription                       |
|   ├── AIOrchestrationService     — NLP intent classification & entity extraction     |
|   ├── ProductMatchingEngine      — 4-tier fuzzy/phonetic product lookup              |
|   ├── BillingEngine              — Draft bill lifecycle (create/confirm/void)        |
|   ├── KhataEngine                — Udhaar/Jama balance computation                  |
|   ├── InventoryEngine            — Manual stock adjustment with audit log            |
|   ├── QueryRouter                — Local SQL vs Cloud LLM query dispatcher           |
|   ├── VoiceFeedbackService       — Hinglish spoken confirmation generator            |
|   └── MerchantCartSession        — In-memory per-store cart state                    |
+---------------------------------------------------------------------------------------+
                                           |
                                    SQLAlchemy ORM
                          (BigInteger with SQLite Integer variant)
                                           v
+---------------------------------------------------------------------------------------+
|                                PERSISTENCE LAYER                                      |
|   Primary: PostgreSQL (Production / Cloud)                                            |
|   Fallback: SQLite (instance/vyapar_saarthi_dev.db — auto-activated on DB failure)    |
+---------------------------------------------------------------------------------------+
```

---

## 2. Application Factory Pattern (`create_app`)

Defined in [app/__init__.py](file:///d:/projectss/Vypaar%20sarthi/app/__init__.py), the factory:

1. **Accepts a config object or dict**: Supports plain `Config` class for production or inline `dict` overrides for test isolation (`TESTING=True`).
2. **Initializes extensions**: `db.init_app()`, `login_manager.init_app()`, `migrate.init_app(app_obj, db)`.
3. **Conditionally loads Sentry**: Only initializes `sentry_sdk` if `SENTRY_DSN` is set **and** does not start with `'mock'` (prevents accidental Sentry calls during testing).
4. **Registers all 15 blueprints**.
5. **Registers a global HTTP 500 error handler** that returns sanitized JSON, preventing stack traces leaking to clients.
6. **Runs database boot sequence** inside `app_obj.app_context()`:
   - Imports all models to register them with SQLAlchemy.
   - Calls `db.create_all()`. If this raises any exception (e.g., PostgreSQL unreachable), it:
     - Overrides `SQLALCHEMY_DATABASE_URI` to `sqlite:///vyapar_saarthi_dev.db`.
     - Calls `db.engine.dispose()` to close dead connection pool.
     - Calls `db.create_all()` again on the SQLite database.
   - If `TESTING` is False and `SEED_DEMO` is True, checks `Product.query.count() == 0` and calls `run_seed_in_context()` from `seed/load_seed.py`.

---

## 3. Database Column Type Strategy

All primary and foreign key columns use:
```python
db.BigInteger().with_variant(db.Integer, "sqlite")
```
This ensures **PostgreSQL receives `BIGINT`** (for scale) while **SQLite falls back to `INTEGER`** (which SQLite requires for `AUTOINCREMENT` primary keys). This is used consistently across all 12 models.

---

## 4. Inventory Architecture: Separation of Concerns

Stock is tracked through **three separate tables** to maintain clean audit trails:

| Table | Purpose |
| :--- | :--- |
| `inventory` | Current `quantity_on_hand` and `low_stock_threshold` (one-to-one with `Product`) |
| `inventory_movements` | Immutable log of every stock change: type (`SALE`, `STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`, `RETURN`), `previous_stock`, `new_stock` |
| `inventory_adjustments` | Owner-only manual correction records with `quantity_delta` and `reason` |

---

## 5. Billing Lifecycle: Draft → Confirm → Transaction

The billing process follows a two-phase commit pattern:

```
Phase 1 — Draft (tentative)
  POST /api/v1/billing/create
  └── Creates DraftBill (line_items_json, subtotal, total)
  └── Checks product existence but does NOT deduct stock yet
  └── Returns draft_bill_id

Phase 2 — Confirm (atomic)
  POST /api/v1/billing/confirm
  ├── Validates idempotency_key against BillingIdempotency table
  ├── If 'udhaar': validates customer_id is provided
  ├── Deducts inventory (checking for INSUFFICIENT_STOCK)
  ├── Creates Transaction + TransactionItem records
  ├── If 'udhaar': creates KhataEntry of type 'credit'
  └── Returns txn_id, invoice_number
```

---

## 6. User Role Architecture

Two roles exist — `'owner'` and `'helper'` — enforced at route level:

```python
@require_role('owner')  # decorator in app/utils/decorators.py
def adjust_inventory(product_id): ...
```

- **Owner**: Full access — can register helpers, adjust inventory manually, view all reports.
- **Helper**: Can create bills, process voice commands, record payments. Cannot adjust stock or register new users.

---

## 7. PWA (Progressive Web App) Support

The `main_bp` blueprint serves two additional routes:
- **`GET /manifest.json`**: Returns a JSON PWA manifest (`name`, `short_name`, `start_url`, `display: standalone`, `theme_color: #0ea5e9`).
- **`GET /sw.js`**: Returns a Network-First Service Worker JavaScript file that enables offline fallback via cache.
