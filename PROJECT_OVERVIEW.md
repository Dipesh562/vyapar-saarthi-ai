# PROJECT_OVERVIEW.md — Vyapar Saarthi AI System Overview

---

## 1. Executive Summary

**Vyapar Saarthi AI** is a voice-first Point of Sale (POS), billing, inventory management, and Khata (customer credit ledger) system engineered for Kirana stores and retail merchants across India.

Merchants can create bills, check stock, and manage customer credit using spoken **Hinglish, Hindi, or English** voice commands. The backend normalizes phonetic Indian product names, fuzzy-matches them against a live catalog, generates itemized draft bills, and deducts inventory automatically on checkout.

---

## 2. Core Business Problems Solved

| Problem | Vyapar Saarthi AI Solution |
| :--- | :--- |
| **Slow counter billing** | Multi-item voice commands converted to draft bills in under 1.5 seconds |
| **Spelling & regional name barriers** | Phonetic + fuzzy matching handles *"Fortune Tel"*, *"Tata Namak"*, *"Cheeni"* |
| **Khata credit tracking errors** | `KhataEntry` records every Udhaar and Jama, linked to specific invoices |
| **Unnoticed stockouts** | `Inventory.is_low_stock` triggers alerts when `quantity_on_hand ≤ low_stock_threshold` |
| **Bulk data entry overhead** | CSV bulk import with header auto-mapping and validation error reporting |
| **Duplicate payment accidents** | `idempotency_key` required on all billing confirm and payment endpoints |

---

## 3. Key Functional Modules

### 🎙️ 1. Voice-First Billing Engine
- **Multi-Modal Input**: Audio uploads (WAV, WebM) via `/api/v1/voice/transcribe` or pre-transcribed text via `/api/v1/voice/process_bill`.
- **AI Intent Classification**: Parses intents: `create_bill`, `add_item`, `remove_item`, `check_stock`, `business_query`.
- **Entity Extraction**: Extracts product names, `quantity`, and measurement units per spoken item.
- **Referential Resolution**: Handles follow-up phrases like *"aur do"* or *"add 2 more"* by resolving to the last matched product via `MerchantCartSession`.
- **Merchant Feedback Learning**: When a merchant clarifies an ambiguous item via `/api/v1/voice/feedback`, the system records a `ProductSynonym` and increments its `evidence_count` for future auto-matching.
- **Spoken Audio Feedback**: `VoiceFeedbackService` generates Hindi/Hinglish confirmation strings read back to the merchant.

### 📦 2. Product Catalog & Inventory Management
- **Product Model**: Stores `name`, `normalized_name`, `price`, `cost_price`, `unit`, `category`, `brand`, `sku`, `barcode`, `image_url`, and `is_active` flag.
- **Separate Inventory Table**: `Inventory` (one-to-one with `Product`) holds `quantity_on_hand`, `low_stock_threshold`, with computed properties `is_low_stock` and `stock_status` (`"in_stock"`, `"low_stock"`, `"out_of_stock"`).
- **Movement Log**: Every stock change (`SALE`, `STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`, `RETURN`) is recorded in `InventoryMovement` with `previous_stock` and `new_stock` for full audit trail.
- **Manual Adjustments**: Owner-only `PATCH /api/v1/inventory/<product_id>` writes an `InventoryAdjustment` record.
- **CSV Bulk Pipeline**: Bulk import/export via `/api/v1/inventory/csv`.

### 💳 3. Customer Khata (Credit Ledger)
- **Customer Profile**: Stores `name` and `phone` (per-store, not globally unique). No built-in `credit_limit` or `current_balance` fields — balance is computed dynamically from `KhataEntry` records.
- **Khata Entry Types**: `'credit'` (Udhaar — goods given on credit) or `'payment'` (Jama — payment collected).
- **Payment Recording**: `POST /api/v1/payments` with mandatory `idempotency_key` to prevent double payments.
- **Every entry is linked to**: `customer_id`, `store_id`, optional `txn_id`, and `recorded_by_user_id`.

### 🧾 4. Billing, Draft Bills & Confirmation
- **Draft Bill Lifecycle**:
  1. `POST /api/v1/billing/create` — Creates a `DraftBill` with JSON line items, `subtotal`, and `total`.
  2. `POST /api/v1/billing/confirm` — Finalizes draft: deducts inventory, creates `Transaction` + `TransactionItem` records, creates `KhataEntry` if `payment_status = 'udhaar'`.
  3. `DELETE /api/v1/billing/<draft_bill_id>` — Voids a draft before confirmation.
- **Idempotency**: `BillingIdempotency` table prevents duplicate `confirm` calls using a `cache_key`.
- **Payment Modes**: `'paid'` (cash/UPI/direct) or `'udhaar'` (credit — requires `customer_id`).
- **Transaction Adjustments**: `TransactionAdjustment` records voids, item corrections, and refunds against confirmed transactions.

### 🛡️ 5. Resilient Infrastructure & Production Operations
- **Self-Healing Database Boot**: Automatically falls back from PostgreSQL to local SQLite if connection fails.
- **Automatic Seed Gate**: Seeds FMCG demo inventory on boot if `Product` table is empty and `SEED_DEMO=true`.
- **User Roles**: `'owner'` (full access) and `'helper'` (no manual stock adjustments or helper management). Enforced via `@require_role('owner')` decorator.
- **PWA Support**: Serves `/manifest.json` and `/sw.js` for Progressive Web App installation on mobile.
- **Error Monitoring**: Optional Sentry SDK integration (skipped if `SENTRY_DSN` starts with `'mock'`).

---

## 4. Technology Stack

```
+-----------------------------------------------------------------------+
|                       VYAPAR SAARTHI AI STACK                         |
+-----------------------------------------------------------------------+
| Backend Framework | Python 3.10+ / Flask (Application Factory)         |
| ORM Layer         | SQLAlchemy (BigInteger/Integer variant for SQLite) |
| Database          | PostgreSQL (Production) / SQLite (Local Fallback)  |
| Migration Engine  | Flask-Migrate / Alembic                            |
| Auth & Security   | Flask-Login, werkzeug.security (Scrypt Hashing)    |
| Role Control      | Custom @require_role('owner') decorator            |
| NLP & Matching    | RapidFuzz, Custom Phonetic Normalizer, Cloud LLMs  |
| Monitoring        | Sentry SDK (Optional, Flask Integration)           |
| Test Framework    | Pytest (30+ Unit & Integration Tests)              |
| PWA               | Service Worker (/sw.js) + Web App Manifest         |
+-----------------------------------------------------------------------+
```

---

## 5. Repository File Structure

```
d:/projectss/Vypaar sarthi/
├── app/                            # Main Application Package
│   ├── models/                     # SQLAlchemy Data Models
│   │   ├── user.py                 # User (owner / helper, phone-based login)
│   │   ├── store.py                # Store (owner_user_id backref, language_pref)
│   │   ├── product.py              # Product (normalized_name, price, is_active)
│   │   ├── product_synonym.py      # ProductSynonym (term, maps_to_product_id, evidence_count)
│   │   ├── inventory.py            # Inventory (quantity_on_hand, low_stock_threshold)
│   │   ├── inventory_movement.py   # InventoryMovement (SALE/STOCK_IN/ADJUSTMENT/RETURN)
│   │   ├── inventory_adjustment.py # InventoryAdjustment (manual owner corrections)
│   │   ├── customer.py             # Customer (name, phone — balance computed from KhataEntry)
│   │   ├── khata.py                # KhataEntry (credit/payment, recorded_by_user_id)
│   │   ├── transaction.py          # Transaction, TransactionItem, TransactionAdjustment
│   │   ├── draft_bill.py           # DraftBill, BillingIdempotency
│   │   └── voice_session.py        # VoiceSession (transcript, resolved_intent, needed_clarification)
│   ├── routes/                     # Flask Blueprint Route Handlers (15 Blueprints)
│   │   ├── main.py                 # main_bp — HTML index, /manifest.json, /sw.js
│   │   ├── auth.py                 # auth_bp — /register_owner, /register_helper, /login, /logout, /me
│   │   ├── voice.py                # voice_bp — /transcribe, /process_bill, /feedback
│   │   ├── billing.py              # billing_bp — /create, /confirm, DELETE /<id>
│   │   ├── products.py             # products_bp — CRUD + search
│   │   ├── inventory.py            # inventory_bp — stock levels, PATCH adjust, history
│   │   ├── inventory_csv.py        # inventory_csv_bp — CSV upload & export
│   │   ├── customers.py            # customers_bp — customer CRUD + khata ledger
│   │   ├── payments.py             # payments_bp — POST /api/v1/payments (idempotent)
│   │   ├── receipts.py             # receipts_bp — invoice generation
│   │   ├── sales.py                # sales_bp — reporting & analytics
│   │   ├── alerts.py               # alerts_bp — low stock notifications
│   │   ├── ai.py                   # ai_bp — direct AI assistant queries
│   │   ├── assistant.py            # assistant_bp — conversation assistant
│   │   └── health.py               # health_bp — /health system status
│   ├── services/                   # Decoupled Core Business Logic
│   │   ├── ai_orchestration.py     # NLP intent & entity extraction
│   │   ├── product_matching.py     # 4-tier fuzzy + phonetic matching engine
│   │   ├── billing_engine.py       # Draft bill creation, confirm, void
│   │   ├── khata_engine.py         # Udhaar/Jama ledger & balance computation
│   │   ├── inventory_engine.py     # Manual stock adjustment logic
│   │   ├── query_router.py         # Local SQL vs Cloud LLM routing
│   │   ├── stt_client.py           # Speech-to-Text audio transcription
│   │   ├── voice_feedback.py       # Hinglish spoken confirmation generator
│   │   └── cart_session.py         # In-memory per-store cart session state
│   ├── utils/
│   │   └── decorators.py           # @require_role('owner') role-based access control
│   ├── extensions.py               # Shared db, login_manager, migrate instances
│   └── __init__.py                 # create_app() factory + DB fallback + seed boot
├── instance/
│   └── vyapar_saarthi_dev.db       # Local SQLite dev database
├── migrations/                     # Alembic migration scripts
├── seed/
│   ├── load_seed.py                # run_seed_in_context() — seeds FMCG demo catalog
│   ├── seed_inventory.csv          # Source CSV seed data
│   └── seed_inventory.sql          # Raw SQL seed script
├── tests/                          # Pytest test suite (30+ tests)
├── .env                            # Environment variable configuration
├── config.py                       # Flask Config class (DB fallback, SEED_DEMO, LLM keys)
├── requirements.txt                # Python package dependencies
├── run.py                          # Server entry point
└── start.bat                       # Windows launch batch script
```
