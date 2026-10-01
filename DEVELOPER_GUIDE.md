# DEVELOPER_GUIDE.md — Setup, Development Standards & Testing

---

## 1. System Requirements

| Requirement | Version / Notes |
| :--- | :--- |
| Python | 3.10+ |
| Database | SQLite 3 (included) or PostgreSQL 14+ |
| OS | Windows, macOS, or Linux |
| Package Installer | pip (included with Python) |

---

## 2. Quickstart (Windows)

```powershell
# Navigate to the project root
cd "d:\projectss\Vypaar sarthi"

# Activate the Python virtual environment
.\venv\Scripts\Activate.ps1

# Install Python dependencies (if adding new packages)
pip install -r requirements.txt

# Start the development server
python run.py

# Alternatively, use the batch launcher:
.\start.bat
```

By default the server runs at: `http://127.0.0.1:5000`

---

## 3. Environment Variable Reference (`.env`)

Copy `.env.example` to `.env` and fill in your values:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `FLASK_ENV` | String | `development` | Sets Flask environment mode |
| `FLASK_DEBUG` | `0` or `1` | `1` | Enables hot-reload & debug output |
| `SECRET_KEY` | String | `dev-secret-key-...` | Session cookie signing key — **change in production** |
| `DATABASE_URL` | URI | `sqlite:///vyapar_saarthi_dev.db` | Primary DB connection. `postgres://` auto-converts to `postgresql://` |
| `SEED_DEMO` | `true`/`false` | `true` | Auto-seeds FMCG demo inventory on first boot |
| `ANTHROPIC_API_KEY` | String | — | Anthropic Claude API key for AI intent & entity extraction (NLP fallback after Gemini) |
| `GEMINI_API_KEY` | String | — | Google Gemini API key for primary NLP intent parsing and Speech-to-Text audio transcription |
| `TWILIO_ACCOUNT_SID` | String | — | Twilio SID (for SMS/WhatsApp receipts if enabled) |
| `TWILIO_AUTH_TOKEN` | String | — | Twilio Auth Token |
| `SENTRY_DSN` | URI | — | Sentry DSN for production error tracking (skipped if starts with `'mock'`) |
| `VOICE_PIPELINE_MODE` | String | `ai_first` | Pipeline mode: `ai_first` or `legacy` |

> [!NOTE]
> **Running Without API Keys**: `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are **completely optional**. If left blank in `.env`, the system automatically defaults to the **Local Kirana Regex Fallback Parser** for NLP and the **Browser Web Speech API** for voice transcription. No cloud API calls are made.

---

## 4. Database Operations

### Automatic Local SQLite Fallback
If `DATABASE_URL` points to an unreachable PostgreSQL server, the application automatically switches to:
```
instance/vyapar_saarthi_dev.db
```
No manual action is required — this happens at startup in `create_app()`.

### Run Alembic Migrations (when model changes are made)
```powershell
flask db migrate -m "Describe what changed in the schema"
flask db upgrade
```

### Manually Seed Demo Inventory
```powershell
python seed/load_seed.py
```
Auto-seeding also runs at boot if `Product` table is empty and `SEED_DEMO=true`.

---

## 5. Test Suite Reference

Vyapar Saarthi AI includes **32 automated tests** using `pytest`.

### Run all tests
```powershell
.\venv\Scripts\pytest
```

### Run with verbose output
```powershell
.\venv\Scripts\pytest -v
```

### Run a single test file
```powershell
.\venv\Scripts\pytest tests/test_billing.py
```

### Test Suite Breakdown

```
tests/
├── test_health.py            ← Health check endpoint verification
├── test_auth.py              ← Registration (owner/helper), login, multi-store switching & deletion
├── test_billing.py           ← Draft creation, confirm (paid & udhaar), stock checks & idempotency
├── test_products.py          ← Product CRUD, barcode & SKU lookup, catalog search
├── test_voice_ai.py          ← AI transcript NLP parsing, intent classification
├── test_voice_pipeline.py    ← End-to-end voice billing (transcribe → process_bill → draft)
├── test_voice_checkpoints.py ← Referential follow-up ("add more"), clarification flow
├── test_assistant_alerts.py  ← Low-stock alert triggers (is_low_stock, stock_status)
└── test_seed_verification.py ← Seed loading integrity — verifies all catalog items are present
```

---

## 6. Development Code Standards

### 1. Always use `create_app()` factory
Never import `app` directly. Use:
```python
from app import create_app
app = create_app()
```

### 2. SQLAlchemy ORM — Never Raw SQL Strings
Always use model queries:
```python
# ✅ Correct (filter_by)
product = Product.query.filter_by(store_id=store_id, sku="TATA-1KG").first()

# ✅ Correct (session.get — PK lookup, SQLAlchemy 2.0 pattern)
store = db.session.get(Store, store_id)

# ❌ Wrong — deprecated as of SQLAlchemy 2.0
store = Store.query.get(store_id)
```

### 3. Protect routes with decorators
```python
@login_required         # any authenticated user
@require_role('owner')  # owner-only route
```

### 4. Separate Business Logic from Route Handlers
Route handlers should only:
- Parse and validate request JSON.
- Call service methods (e.g. `BillingEngine.create_draft_bill(...)`).
- Return JSON responses with appropriate HTTP status codes.

All business logic (calculations, DB writes, entity lookups) belongs in `app/services/`.

### 5. BigInteger / SQLite Compatibility
When adding new FK or PK columns, always use:
```python
db.BigInteger().with_variant(db.Integer, "sqlite")
```
This ensures PostgreSQL gets `BIGINT` and SQLite gets `INTEGER` (required for auto-increment PKs).

### 6. Idempotency Keys
Any endpoint that writes financial data (bill confirmations, payments) must:
- Accept an `idempotency_key` in the request body.
- Check against `BillingIdempotency.cache_key` or `IDEMPOTENCY_CACHE` before writing.
- Return the cached response if the key already exists.

### 7. Timezone-Aware Datetimes
Always use timezone-aware UTC datetimes (Python 3.11+ requirement):
```python
# ✅ Correct
from datetime import datetime, timezone
now = datetime.now(timezone.utc)

# ❌ Deprecated (Python 3.12+)
now = datetime.utcnow()
```

In SQLAlchemy models, use `lambda:` to pass a callable:
```python
created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
```
