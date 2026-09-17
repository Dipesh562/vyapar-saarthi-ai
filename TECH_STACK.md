# TECH_STACK.md — Complete Technology Stack Reference

> Everything your code is built on, explained clearly — what each technology is,
> why it was chosen, and exactly how it is used in Vyapar Saarthi AI.

---

## Table of Contents

1. [Backend Web Framework — Flask](#1-backend-web-framework--flask)
2. [Database Layer — SQLAlchemy ORM](#2-database-layer--sqlalchemy-orm)
3. [Database Engines — PostgreSQL & SQLite](#3-database-engines--postgresql--sqlite)
4. [Database Migrations — Flask-Migrate & Alembic](#4-database-migrations--flask-migrate--alembic)
5. [Authentication & Session Management — Flask-Login](#5-authentication--session-management--flask-login)
6. [Password Security — werkzeug.security](#6-password-security--werkzeugsecurity)
7. [Role-Based Access Control — Custom Decorator](#7-role-based-access-control--custom-decorator)
8. [AI Intent Parsing — Anthropic Claude & Google Gemini](#8-ai-intent-parsing--anthropic-claude--google-gemini)
9. [Speech-to-Text — Gemini Multimodal Audio API](#9-speech-to-text--gemini-multimodal-audio-api)
10. [Fuzzy Product Matching — RapidFuzz](#10-fuzzy-product-matching--rapidfuzz)
11. [Unicode & Devanagari Normalization — Unidecode](#11-unicode--devanagari-normalization--unidecode)
12. [Environment Variables — python-dotenv](#12-environment-variables--python-dotenv)
13. [MySQL Driver — PyMySQL](#13-mysql-driver--pymysql)
14. [PostgreSQL Driver — psycopg2-binary](#14-postgresql-driver--psycopg2-binary)
15. [HTTP Client — requests](#15-http-client--requests)
16. [SMS & WhatsApp Receipts — Twilio](#16-sms--whatsapp-receipts--twilio)
17. [Error Monitoring — Sentry SDK](#17-error-monitoring--sentry-sdk)
18. [Production Server — Gunicorn](#18-production-server--gunicorn)
19. [Test Framework — Pytest](#19-test-framework--pytest)
20. [PWA Support — Service Worker & Manifest](#20-pwa-support--service-worker--manifest)
21. [In-Memory Cart Sessions](#21-in-memory-cart-sessions)
22. [Decimal Arithmetic for Financial Data](#22-decimal-arithmetic-for-financial-data)

---

## 1. Backend Web Framework — Flask

### What is it?
Flask is a **lightweight Python web framework**. It handles incoming HTTP requests, routes them to the correct function (called a "view" or "route handler"), and sends back HTTP responses.

### Why Flask?
- Very lightweight — no unnecessary features bundled in.
- Extremely flexible and easy to extend with plugins.
- Perfect for JSON REST APIs (which is what this project is).
- The **Application Factory Pattern** it supports makes the code clean and testable.

### How it's used
The entire application is created through `create_app()` in [app/__init__.py](file:///d:/projectss/Vypaar%20sarthi/app/__init__.py):

```python
from flask import Flask
app_obj = Flask(__name__)
```

**Blueprints** are Flask's way of splitting a large application into smaller pieces. Each feature area (auth, billing, voice, inventory) has its own Blueprint:

```python
auth_bp    = Blueprint('auth', __name__, url_prefix='/api/v1/auth')
voice_bp   = Blueprint('voice', __name__, url_prefix='/api/v1/voice')
billing_bp = Blueprint('billing', __name__, url_prefix='/api/v1/billing')
# ... 15 blueprints total
```

Every blueprint is registered with the main app:
```python
app_obj.register_blueprint(auth_bp)
app_obj.register_blueprint(voice_bp)
```

| Package | Version Required |
| :--- | :--- |
| `Flask` | >= 3.0.0 |

---

## 2. Database Layer — SQLAlchemy ORM

### What is it?
SQLAlchemy is an **Object-Relational Mapper (ORM)** for Python. Instead of writing raw SQL strings, you define your database tables as Python classes (called Models), and SQLAlchemy translates all operations into SQL automatically.

### Why SQLAlchemy?
- Prevents SQL injection attacks — all queries are parameterized automatically.
- Makes switching database engines (e.g., from SQLite to PostgreSQL) trivial.
- Relationships between tables (e.g., Customer → KhataEntry) are handled as Python object properties.

### How it's used
All 15 database tables are defined as Python classes in `app/models/`. Example — the `Product` model:

```python
class Product(db.Model):
    __tablename__ = 'products'
    product_id    = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    name          = db.Column(db.String(150), nullable=False)
    price         = db.Column(db.Numeric(10, 2), nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
```

**Querying** is done in plain Python — no SQL strings:
```python
# Find an active product by ID for a specific store
product = Product.query.filter_by(product_id=1, store_id=2, is_active=True).first()

# Read a property
print(product.price)   # 140.00
```

**BigInteger with SQLite variant** — every primary/foreign key uses this pattern:
```python
db.BigInteger().with_variant(db.Integer, "sqlite")
```
This gives PostgreSQL a `BIGINT` (64-bit integer, handles billions of records) while giving SQLite a regular `INTEGER` (required for SQLite's auto-increment to work). This is why the app runs on both databases seamlessly.

**The shared `db` instance** is created once in [app/extensions.py](file:///d:/projectss/Vypaar%20sarthi/app/extensions.py) and shared across all models and services:
```python
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()   # initialized once; bound to app later via db.init_app()
```

| Package | Version Required |
| :--- | :--- |
| `Flask-SQLAlchemy` | >= 3.1.0 |

---

## 3. Database Engines — PostgreSQL & SQLite

### PostgreSQL (Production)
**What it is**: A powerful, industry-standard open-source relational database used in production deployments on cloud servers.

**Why**: Handles large transaction volumes, supports `BIGINT` for primary keys, supports concurrent reads/writes from multiple users, and has robust data integrity features.

**Connection**: Configured via `DATABASE_URL` environment variable. If the URL starts with `postgres://` (old Heroku format), it is automatically converted to `postgresql://`:
```python
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
```

### SQLite (Local Development & Automatic Fallback)
**What it is**: A file-based database that requires zero server setup. The entire database is stored in a single file: `instance/vyapar_saarthi_dev.db`.

**Why**: Perfect for local development and automated testing — no database server to install or configure.

**Self-Healing Fallback** — If PostgreSQL is unreachable at startup, the app automatically switches to SQLite:
```python
try:
    db.create_all()
except Exception:
    app_obj.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vyapar_saarthi_dev.db'
    db.engine.dispose()   # close broken connection pool
    db.create_all()       # re-create tables on SQLite
```

| Package | Version Required | Purpose |
| :--- | :--- | :--- |
| `psycopg2-binary` | >= 2.9.0 | PostgreSQL database driver (C extension) |
| `PyMySQL` | >= 1.1.0 | MySQL-compatible driver (if MySQL is used) |

---

## 4. Database Migrations — Flask-Migrate & Alembic

### What is it?
**Alembic** is a database migration tool. **Flask-Migrate** is the Flask wrapper around Alembic.

A "migration" is a versioned script that modifies your database schema (add column, rename table, add index, etc.) in a controlled way. Think of it like `git` for your database structure.

### Why use it?
Without migrations, every schema change would require manually running SQL statements on every environment (dev, staging, production). Migrations automate this and keep all environments in sync.

### How it's used
Initialize and run migrations with:
```powershell
flask db migrate -m "Add language_pref to stores"   # auto-generates migration script
flask db upgrade                                      # applies pending migrations to DB
flask db downgrade                                    # rolls back last migration
```

Migration scripts are stored in the `migrations/versions/` folder. Alembic tracks which migrations have been applied using a `alembic_version` table in the database.

| Package | Version Required |
| :--- | :--- |
| `Flask-Migrate` | >= 4.0.5 |

---

## 5. Authentication & Session Management — Flask-Login

### What is it?
**Flask-Login** manages user sessions in Flask apps. It tracks which user is currently logged in and provides the `@login_required` decorator to protect routes.

### Why use it?
- Handles session persistence across requests via encrypted cookies.
- Makes the currently logged-in user available as `current_user` anywhere in the code.
- Provides clean `login_user()` and `logout_user()` functions.

### How it's used

**Shared instance** in [app/extensions.py](file:///d:/projectss/Vypaar%20sarthi/app/extensions.py):
```python
from flask_login import LoginManager
login_manager = LoginManager()
```

**Custom unauthorized handler** — when an unauthenticated request hits a protected endpoint, instead of redirecting to an HTML login page (Flask's default), it returns a clean JSON error:
```python
@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}}), 401
```

**User model** implements `UserMixin` and a `get_id()` method:
```python
class User(UserMixin, db.Model):
    def get_id(self):
        return str(self.user_id)
```

**Protecting routes**:
```python
@voice_bp.route('/process_bill', methods=['POST'])
@login_required   # ← returns 401 JSON if not logged in
def process_voice_bill():
    user_store = current_user.store_id   # ← always available in protected routes
```

**Cookie security settings** in `config.py`:
```python
SESSION_COOKIE_HTTPONLY = True     # JS cannot read the cookie (XSS protection)
SESSION_COOKIE_SAMESITE = 'Lax'   # Not sent on cross-site POSTs (CSRF protection)
```

| Package | Version Required |
| :--- | :--- |
| `Flask-Login` | >= 0.6.3 |

---

## 6. Password Security — werkzeug.security

### What is it?
`werkzeug` is a utility library bundled with Flask. Its `security` module provides cryptographic password hashing.

### Why use Scrypt?
Passwords are **never stored as plain text**. They are hashed using the **Scrypt** algorithm — a modern, memory-hard hashing algorithm that is extremely resistant to brute-force and GPU cracking attacks.

### How it's used

In [app/models/user.py](file:///d:/projectss/Vypaar%20sarthi/app/models/user.py):
```python
from werkzeug.security import generate_password_hash, check_password_hash

def set_password(self, password):
    self.password_hash = generate_password_hash(password)
    # Stores something like: "scrypt:32768:8:1$salt$hashedvalue"

def check_password(self, password):
    return check_password_hash(self.password_hash, password)
    # Returns True only if the input matches the stored hash
```

This means even if the database is ever compromised, no real passwords are exposed.

*(werkzeug is installed automatically as part of Flask — no separate package needed)*

---

## 7. Role-Based Access Control — Custom Decorator

### What is it?
A custom Python decorator defined in [app/utils/decorators.py](file:///d:/projectss/Vypaar%20sarthi/app/utils/decorators.py) that restricts certain routes to specific user roles.

### User Roles
There are exactly two roles in the system:
- **`'owner'`**: Full access — can adjust inventory, register helpers, view all reports.
- **`'helper'`**: Limited access — can create bills, process voice commands, record payments.

### How it's used

```python
from app.utils.decorators import require_role

@inventory_bp.route('/<int:product_id>', methods=['PATCH'])
@require_role('owner')   # Only owners can manually adjust stock
def adjust_inventory(product_id):
    ...
```

Internally, `@require_role` checks:
1. Is the user authenticated? → If not, returns `401 UNAUTHORIZED`.
2. Is their role in the allowed list? → If not, returns `403 FORBIDDEN_ROLE`.
3. If both pass → executes the route function normally.

*(This is pure Python — no additional package required)*

---

## 8. AI Intent Parsing — Anthropic Claude & Google Gemini

### What is it?
Two cloud Large Language Model (LLM) APIs that parse spoken merchant transcripts into structured JSON.

### Why Two AI Providers?
Redundancy and cost optimization. The system tries providers in order:
1. **Google Gemini** (tried first — faster, cheaper)
2. **Anthropic Claude** (fallback if Gemini fails or key is missing)
3. **Regex Fallback Parser** (local, zero-cost fallback if both AI providers fail)

### What these LLMs actually do
Given a spoken transcript like:
> *"Do packet Fortune Oil aur ek kilo Tata Namak Ramesh ka udhaar"*

The LLM returns structured JSON:
```json
{
  "intent": "create_bill",
  "items": [
    { "raw_text": "Fortune Oil", "quantity": 2, "unit": "packet", "is_reference": false },
    { "raw_text": "Tata Namak",  "quantity": 1, "unit": "kg",     "is_reference": false }
  ],
  "customer_name": "Ramesh",
  "payment_status": "udhaar",
  "confidence": 0.97,
  "needs_clarification": false
}
```

### The System Prompt
The LLM is given a precise **system prompt** that defines exactly what JSON schema to output, how to handle Hindi/Marathi quantities (*"do kilo"* → `quantity: 2, unit: "kg"`), and when to set `is_reference: true` for follow-up phrases.

### Gemini models tried (in order)
```python
for model_name in ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-flash-latest']:
    # tries each model, moves to next on failure
```

### Claude model used
```python
model="claude-3-5-sonnet-20241022"
```

### Pipeline Modes
Controlled by `VOICE_PIPELINE_MODE` environment variable:
- **`ai_first`** (default): Preprocess transcript → try Gemini → try Claude → regex fallback.
- **`legacy`**: Try regex first → if nothing found, try Gemini → try Claude → regex fallback.

| Package | Version Required | Provider |
| :--- | :--- | :--- |
| `anthropic` | >= 0.18.0 | Anthropic (Claude) |
| `google-genai` | >= 0.1.0 | Google (Gemini) |

---

## 9. Speech-to-Text — Gemini Multimodal Audio API

### What is it?
**Speech-to-Text (STT)** converts an audio recording of a merchant's spoken command into a text transcript.

### Why Gemini for STT?
Google's Gemini models support **multimodal input** — they can directly process audio bytes and return text. This avoids needing a separate Whisper or Google Speech-to-Text service. It also handles **Hindi, Marathi, Hinglish, and Indian-accented English** natively.

### How it's used — [app/services/stt_client.py](file:///d:/projectss/Vypaar%20sarthi/app/services/stt_client.py)

```
[Audio bytes: WAV / WebM / MP3 / OGG / M4A]
            |
            v
  Gemini multimodal API
  (gemini-2.0-flash → gemini-1.5-flash as fallback)
            |
            v
  Returns JSON: { "transcript": "...", "confidence": 0.95, "language_detected": "hi-IN" }
```

The audio bytes are passed directly as a `types.Part`:
```python
audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
response = client.models.generate_content(model="gemini-2.0-flash", contents=[audio_part, prompt])
```

**Language detection output**: `"hi-IN"` (Hindi), `"mr-IN"` (Marathi), or `"en-IN"` (Indian English).

**Confidence threshold**: If confidence < 0.60, the transcript is rejected and a retry prompt is returned.

**Graceful degradation**: If `GEMINI_API_KEY` is not set (or starts with `'mock'`), the STT client returns `{"error": "STT_UNAVAILABLE"}` — development and testing still works using the `transcript_text` form field bypass.

---

## 10. Fuzzy Product Matching — RapidFuzz

### What is it?
**RapidFuzz** is a fast Python string similarity library. It measures how similar two strings are, returning a score from 0% (completely different) to 100% (identical).

### Why RapidFuzz?
Indian retail product names have extremely high variation — *"Fortune"* might be spoken as *"Forchun"*, *"Forchoon"*, or *"Fortun"*. RapidFuzz handles all of these without requiring exact spelling.

RapidFuzz is written in C++ under the hood — it is 10–100× faster than Python-native alternatives like `fuzzywuzzy`.

### How it's used — [app/services/product_matching.py](file:///d:/projectss/Vypaar%20sarthi/app/services/product_matching.py)

```python
from rapidfuzz import fuzz

score = fuzz.token_sort_ratio("fortune oil", "oil fortune sunlite 1l")
# → 87.0  (high similarity even though word order differs)
```

**`token_sort_ratio`**: Sorts both strings alphabetically by word before comparing. This makes *"Fortune Oil 1L"* and *"Oil Fortune 1L"* score 100% instead of a lower partial match.

**Scoring thresholds applied**:
```
≥ 85% → Auto-match (product added to cart automatically)
60–84% → Ambiguous (ask merchant to confirm from candidates)
< 60%  → Not found (ask merchant to re-speak or search)
```

| Package | Version Required |
| :--- | :--- |
| `rapidfuzz` | >= 3.6.0 |

---

## 11. Unicode & Devanagari Normalization — Unidecode

### What is it?
**Unidecode** is a Python library that converts Unicode characters (like Hindi Devanagari script: `आशीर्वाद`) into their closest ASCII/Roman equivalent (`Ashirvaad`).

### Why is it needed?
Merchants can speak product names in Hindi script, regional Roman transliterations, or plain English — all of which need to map to the same product in the database.

### How it's used

**In `Product.normalize_product_name()`** — called automatically when a product is created:
```python
from unidecode import unidecode

def normalize_product_name(raw_name: str) -> str:
    raw_name = unidecode(raw_name)           # "आटा"   → "Aata"
    cleaned  = raw_name.lower()              # "Aata"  → "aata"
    cleaned  = re.sub(r'[^\w\s]', '', cleaned)  # remove punctuation
    return re.sub(r'\s+', ' ', cleaned).strip() # collapse spaces
```

**In the Devanagari mapping table** — the matching engine has a 100+ term map:
```python
DEVANAGARI_KIRANA_MAP = {
    'तेल': 'oil',    # Hindi for "oil"
    'चीनी': 'sugar', # Hindi for "sugar"
    'नमक': 'salt',   # Hindi for "salt"
    'फॉर्चून': 'fortune',
    'अमूल': 'amul',
    # ... and 80+ more entries covering Hindi + Marathi
}
```

This map covers both generic product types (oil, sugar, salt) **and** brand names in Devanagari (*Fortune*, *Amul*, *Patanjali*, *Tata*, *Parle*), plus both Hindi and Marathi variants.

| Package | Version Required |
| :--- | :--- |
| `unidecode` | >= 1.3.0 |

---

## 12. Environment Variables — python-dotenv

### What is it?
`python-dotenv` reads key=value pairs from a `.env` file and loads them into `os.environ` at startup.

### Why use it?
Environment variables keep secrets (API keys, database URLs, session secret keys) **out of source code**. You never commit `.env` to version control.

### How it's used — [config.py](file:///d:/projectss/Vypaar%20sarthi/config.py)
```python
from dotenv import load_dotenv
load_dotenv()  # reads .env file before any config is accessed

class Config:
    SECRET_KEY       = os.environ.get('SECRET_KEY', 'dev-secret-key-...')
    DATABASE_URL     = os.environ.get('DATABASE_URL', 'sqlite:///...')
    GEMINI_API_KEY   = os.environ.get('GEMINI_API_KEY')
    ANTHROPIC_API_KEY= os.environ.get('ANTHROPIC_API_KEY')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    VOICE_PIPELINE_MODE = os.environ.get('VOICE_PIPELINE_MODE', 'ai_first')
```

| Package | Version Required |
| :--- | :--- |
| `python-dotenv` | >= 1.0.0 |

---

## 13. MySQL Driver — PyMySQL

### What is it?
A pure-Python MySQL database driver. Allows SQLAlchemy to connect to MySQL/MariaDB databases.

### Why is it included?
Provides flexibility — if a MySQL-compatible database is used as the primary store (instead of PostgreSQL), SQLAlchemy routes through PyMySQL automatically.

| Package | Version Required |
| :--- | :--- |
| `PyMySQL` | >= 1.1.0 |

---

## 14. PostgreSQL Driver — psycopg2-binary

### What is it?
The standard Python adapter for PostgreSQL. The `-binary` suffix means it ships with compiled C extensions pre-bundled — no additional system-level PostgreSQL libraries need to be installed.

### Why use it?
Required for SQLAlchemy to communicate with PostgreSQL in production. Without it, the `postgresql://` database URL would fail to connect.

| Package | Version Required |
| :--- | :--- |
| `psycopg2-binary` | >= 2.9.0 |

---

## 15. HTTP Client — requests

### What is it?
`requests` is the most popular Python library for making HTTP requests to external APIs.

### How it's used
Used by internal services when calling any external webhook, callback URL, or third-party REST API that does not have a dedicated Python SDK.

| Package | Version Required |
| :--- | :--- |
| `requests` | >= 2.31.0 |

---

## 16. SMS & WhatsApp Receipts — Twilio

### What is it?
**Twilio** is a cloud communications platform. It provides APIs to send SMS messages and WhatsApp messages programmatically.

### How it's used
After a bill is confirmed and a receipt is generated, Twilio can send the customer a digital invoice via:
- **SMS**: Standard text message with bill summary.
- **WhatsApp**: Rich message with itemized invoice via WhatsApp Business API.

Configured via environment variables:
```ini
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
```

| Package | Version Required |
| :--- | :--- |
| `twilio` | >= 8.0.0 |

---

## 17. Error Monitoring — Sentry SDK

### What is it?
**Sentry** is a cloud-based application monitoring and error tracking platform. When an unexpected exception or crash happens in production, Sentry captures the full stack trace, request context, user info, and environment — and sends an alert.

### Why use it?
Without Sentry, production bugs are invisible. With it, developers know exactly which endpoint failed, what the error was, and which user triggered it — within seconds of it happening.

### How it's initialized — [app/__init__.py](file:///d:/projectss/Vypaar%20sarthi/app/__init__.py)
```python
sentry_dsn = os.environ.get('SENTRY_DSN')
if sentry_dsn and not sentry_dsn.startswith('mock'):  # skipped in testing
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.2   # records 20% of requests for performance tracing
    )
```

**Client-side protection**: A global 500 error handler is registered to prevent raw Python stack traces from being returned to users:
```python
@app_obj.errorhandler(500)
def handle_internal_server_error(e):
    return {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "..."}}, 500
```
The full error details still go to Sentry in the background.

| Package | Version Required |
| :--- | :--- |
| `sentry-sdk[flask]` | >= 1.40.0 |

---

## 18. Production Server — Gunicorn

### What is it?
**Gunicorn** (Green Unicorn) is a production-grade Python WSGI HTTP server. Flask's built-in development server (`flask run` or `python run.py`) is **not suitable for production** — it handles one request at a time and has no worker management.

### Why Gunicorn?
- Spawns multiple **worker processes** to handle concurrent requests simultaneously.
- Managed by cloud platforms (Render, Railway, Heroku) via the `Procfile`.
- Significantly more stable and performant than Flask's dev server.

### How it's used
The `Procfile` (used by cloud deployment platforms) specifies:
```
web: gunicorn run:app
```
This tells the platform to start Gunicorn, pointing it to the `app` object exported by `run.py`.

For local production-like testing:
```powershell
gunicorn -w 4 run:app   # 4 worker processes
```

| Package | Version Required |
| :--- | :--- |
| `gunicorn` | >= 21.2.0 |

---

## 19. Test Framework — Pytest

### What is it?
**Pytest** is Python's most popular testing framework. It discovers and runs test files automatically, provides clean assertion messages, and supports fixtures (reusable test setup logic).

### Test Suite Overview

```
tests/
├── test_auth.py              ← Registration, login, /me endpoint, role checks
├── test_billing.py           ← Draft creation, confirm, idempotency, insufficient stock
├── test_products.py          ← Catalog CRUD, search, barcode lookup
├── test_voice_ai.py          ← NLP intent parsing and entity extraction
├── test_voice_pipeline.py    ← Full voice billing flow (transcribe → draft)
├── test_voice_checkpoints.py ← Referential follow-up ("aur do"), clarification flow
├── test_assistant_alerts.py  ← Low-stock alert triggers
└── test_seed_verification.py ← Seed catalog integrity verification
```

### How to run
```powershell
.\venv\Scripts\pytest          # run all 30+ tests
.\venv\Scripts\pytest -v       # verbose output (shows each test name)
.\venv\Scripts\pytest tests/test_billing.py   # run a single file
```

The test configuration uses `create_app({'TESTING': True, ...})` to:
- Override the database to an in-memory SQLite database.
- Disable SEED_DEMO to prevent demo data from loading.
- Mock LLM API keys so no real API calls are made.

| Package | Version Required |
| :--- | :--- |
| `pytest` | >= 8.0.0 |

---

## 20. PWA Support — Service Worker & Manifest

### What is it?
A **Progressive Web App (PWA)** is a website that can be installed on a user's phone or computer and behaves like a native app (works offline, has an icon, runs in full-screen).

### How it's used — [app/routes/main.py](file:///d:/projectss/Vypaar%20sarthi/app/routes/main.py)

**Web App Manifest** (`GET /manifest.json`):
```json
{
  "name": "Vyapar Saarthi - AI Kirana Assistant",
  "short_name": "VyaparSaarthi",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#0ea5e9",
  "background_color": "#ffffff"
}
```

**Service Worker** (`GET /sw.js`):
A JavaScript file that browsers install to intercept network requests. It implements a **Network-First** strategy — always tries the network, falls back to browser cache if offline. This means the POS keeps working even during brief internet drops at the counter.

*(Pure Flask routes — no additional package required)*

---

## 21. In-Memory Cart Sessions

### What is it?
`MerchantCartSession` in [app/services/cart_session.py](file:///d:/projectss/Vypaar%20sarthi/app/services/cart_session.py) is a **class-level Python dictionary** that stores active cart state for each store.

### Why not use the database for cart state?
Cart state during voice billing is transient — it changes with every voice command. Writing every intermediate state to the database would be slow and create enormous amounts of throwaway data. In-memory storage is instant.

### How it works
```python
class MerchantCartSession:
    _sessions: Dict[int, Dict[str, Any]] = {}  # key = store_id
```

Each session entry stores:
- `cart` — list of current matched items
- `last_referenced_item` — last product spoken (for *"aur do"* resolution)
- `last_referenced_customer` — last customer spoken
- `last_active` — timestamp for timeout tracking

**15-Minute Inactivity Timeout**: Sessions automatically expire if inactive for 15 minutes. This is enforced lazily — checked whenever the session is accessed, not on a background timer.

*(Pure Python — no additional package required)*

---

## 22. Decimal Arithmetic for Financial Data

### What is it?
Python's built-in `decimal.Decimal` class for arbitrary-precision arithmetic.

### Why not use `float`?
Floating-point numbers cannot represent most decimal fractions exactly:
```python
>>> 0.1 + 0.2
0.30000000000000004   # Wrong! Would cause billing errors.

>>> Decimal('0.1') + Decimal('0.2')
Decimal('0.3')        # Correct!
```

### How it's used throughout billing
All monetary calculations in `BillingEngine` and `KhataEngine` use `Decimal`:
```python
unit_price   = Decimal(str(product.price))        # never pass float directly
requested_qty = Decimal(str(item.get('quantity'))) # always convert via str first
line_total   = requested_qty * unit_price          # Decimal × Decimal = Decimal
```

All database `price`, `total`, `amount` columns are defined as `Numeric(10, 2)` (10 digits, 2 decimal places) — SQLAlchemy maps these to Python `Decimal` automatically.

*(Built into Python standard library — no additional package required)*

---

## Full Dependency Summary

```
requirements.txt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Flask>=3.0.0              Web framework & routing
Flask-SQLAlchemy>=3.1.0   ORM layer — Python classes to SQL
Flask-Login>=0.6.3        Session auth & @login_required
Flask-Migrate>=4.0.5      DB schema versioning (Alembic)
PyMySQL>=1.1.0            MySQL database driver
psycopg2-binary>=2.9.0    PostgreSQL database driver
python-dotenv>=1.0.0      .env file loader
rapidfuzz>=3.6.0          Fast fuzzy string matching
anthropic>=0.18.0         Anthropic Claude API client
google-genai>=0.1.0       Google Gemini API client (STT + NLP)
requests>=2.31.0          HTTP client for external APIs
twilio>=8.0.0             SMS/WhatsApp receipt delivery
sentry-sdk[flask]>=1.40.0 Production error monitoring
gunicorn>=21.2.0          Production WSGI server
unidecode>=1.3.0          Unicode → ASCII transliteration
pytest>=8.0.0             Automated testing framework
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Built-in (no install needed):
  decimal    Precise financial arithmetic
  uuid       Unique draft_bill_id / session_id generation
  json       JSON serialization for line_items_json
  re         Regex for transcript normalization
  time       Cart session 15-min inactivity timeout
  functools  @wraps in custom decorators
```
