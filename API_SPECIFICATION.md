# API_SPECIFICATION.md — REST API Endpoint Specification

> **Current Working Condition**: Fully maps all 16 Flask Blueprints registered in [app/__init__.py](file:///d:/projectss/Vypaar%20sarthi/app/__init__.py).

---

## 1. Global API Conventions

### Base URL & Versioning
All application business API endpoints are routed under `/api/v1/` except `/health`, `/`, `/manifest.json`, and `/sw.js`.

### Authentication
- Session-based authentication powered by `Flask-Login`.
- Authentication via `POST /api/v1/auth/login` (phone number + password).
- Protected endpoints require a valid session cookie (`session`). Unauthorized requests receive `401 UNAUTHORIZED`.

### Multi-Store Context Resolution
Endpoints determine the active store context using `get_active_store_id()`, which prioritizes:
1. `session['active_store_id']`
2. `X-Store-ID` HTTP header
3. Current logged-in user's primary assigned store (`current_user.store_id`)

### Role-Based Access Control
Routes protected by `@require_role('owner')` are restricted to store owners:
- Product creation, editing, and soft deletion (`/api/v1/products`)
- Manual stock adjustments (`PATCH /api/v1/inventory/<product_id>`)
- CSV catalog import (`/api/v1/products/import/*`)
- Store management (`/api/v1/stores/*`)
- Sales summary analytics (`/api/v1/sales/summary`)
- Registering helper staff (`POST /api/v1/auth/register_helper`)

### Standard Error Format
```json
{
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Human-readable explanation."
  }
}
```

---

## 2. Authentication (`/api/v1/auth`)

### `POST /api/v1/auth/register_owner`
Creates a primary store, registers the owner user account, links them via `OwnerStore`, and logs in immediately.
- **Request**:
  ```json
  {
    "store_name": "Sharma Kirana",
    "name": "Ramesh Sharma",
    "phone": "9876543210",
    "password": "SecurePass123",
    "address": "MG Road, Delhi",
    "language_pref": "hi-en"
  }
  ```
- **Response** `201 Created`:
  ```json
  {
    "message": "Owner registered successfully.",
    "user": {
      "user_id": 1,
      "name": "Ramesh Sharma",
      "role": "owner",
      "store_id": 1,
      "store_name": "Sharma Kirana"
    }
  }
  ```

### `POST /api/v1/auth/register_helper` *(Owner only)*
Registers a helper staff user for the owner's active store.
- **Request**: `{"name": "Suresh", "phone": "9876540000", "password": "helper123"}`
- **Response** `201 Created`: Returns user object with role `'helper'`.

### `POST /api/v1/auth/login`
Phone and password authentication.
- **Request**: `{"phone": "9876543210", "password": "SecurePass123"}`
- **Response** `200 OK`:
  ```json
  {
    "message": "Logged in successfully.",
    "user": {
      "user_id": 1,
      "name": "Ramesh Sharma",
      "role": "owner",
      "store_id": 1
    }
  }
  ```

### `POST /api/v1/auth/logout`
Clears session cookie and logs out current user.
- **Response** `200 OK`: `{"message": "Logged out successfully."}`

### `GET /api/v1/auth/me`
Returns current authenticated user details and active store ID.
- **Response** `200 OK`: `{"user_id": 1, "name": "Ramesh Sharma", "role": "owner", "store_id": 1, "active_store_id": 1}`

### `GET /api/v1/auth/my_stores`
List all stores accessible to the logged-in owner.
- **Response** `200 OK`: Array of accessible store summaries.

### `POST /api/v1/auth/add_store`
Quickly creates and attaches a new store to the authenticated owner.
- **Request**: `{"store_name": "Sharma Kirana Branch", "address": "Market Yard", "phone": "9876543211"}`
- **Response** `201 Created`: Details of the created store.

### `POST /api/v1/auth/switch_store`
Switches active store context in the session.
- **Request**: `{"store_id": 2}`
- **Response** `200 OK`: `{"message": "Switched active store", "active_store_id": 2}`

---

## 3. Store Management (`/api/v1/stores`)

### `GET /api/v1/stores`
Returns all active store outlets belonging to the authenticated owner.
- **Response** `200 OK`:
  ```json
  {
    "stores": [
      {
        "store_id": 1,
        "name": "Sharma Kirana Main",
        "phone": "9876543210",
        "address": "MG Road",
        "is_primary": true,
        "is_active": true,
        "is_active_now": true
      }
    ],
    "active_store_id": 1,
    "total": 1
  }
  ```

### `POST /api/v1/stores`
Creates a new store and automatically activates it in the session.
- **Request**: `{"store_name": "Sharma Kirana Branch 2", "address": "Station Rd", "phone": "9876543212", "gstin": "27AAAAA0000A1Z5"}`
- **Response** `201 Created`: `{"message": "Store created successfully.", "store": {...}, "active_store_id": 2}`

### `GET /api/v1/stores/<int:store_id>`
Fetches details of a specific owned store.
- **Response** `200 OK` or `404 STORE_NOT_FOUND`.

### `PATCH /api/v1/stores/<int:store_id>`
Updates store metadata (name, address, phone, gstin, language_pref).
- **Response** `200 OK`.

### `POST /api/v1/stores/<store_id>/switch` (or `/switch/<store_id>`)
Switches active session store context.
- **Response** `200 OK`: `{"message": "Switched to store ...", "active_store_id": 2}`

### `DELETE /api/v1/stores/<int:store_id>`
Soft-deletes a store (`is_active = False`). Disallowed for primary stores or if it's the owner's last remaining active store.
- **Response** `200 OK`: `{"message": "Store deleted successfully", "active_store_id": 1}`

---

## 4. Voice Billing (`/api/v1/voice`)

### `POST /api/v1/voice/transcribe`
Accepts an audio file or direct text override, transcribes via Google Gemini Multimodal STT, and creates a `VoiceSession` record.
- **Request** (multipart/form-data):
  - `audio`: Binary audio file (WAV, WebM, MP3, OGG, M4A)
  - `transcript_text`: *(Optional)* Text override for testing/bypass
  - `language_hint`: *(Optional)* `"hi-IN"`, `"mr-IN"`, or `"en-IN"`
  - `session_id`: *(Optional)* Existing UUID string
- **Response** `200 OK`:
  ```json
  {
    "session_id": "8a32f912-12bc-4421-a123-99b821a711ef",
    "transcript": "Do packet Fortune Oil aur ek kilo Tata Namak",
    "confidence": 0.95
  }
  ```
- **Error** `422` if confidence < 0.60: `{"error": {"code": "LOW_CONFIDENCE_TRANSCRIPTION", ...}}`

### `POST /api/v1/voice/process_bill`
End-to-end voice billing processor: parses intent → matches products → creates/merges `DraftBill`.
- **Request**:
  ```json
  {
    "transcript": "Do packet Fortune Oil aur ek kilo Tata Namak",
    "session_id": "8a32f912-...",
    "draft_bill_id": "optional-draft-uuid"
  }
  ```
- **Response** `201 Created` (Draft Bill Created):
  ```json
  {
    "session_id": "8a32f912-...",
    "status": "draft_created",
    "payment_status": "paid",
    "draft_bill": {
      "draft_bill_id": "xyz789",
      "line_items": [
        { "product_id": 1, "name": "Fortune Sunlite Oil 1L", "quantity": 2, "unit_price": 140.0, "line_total": 280.0 }
      ],
      "subtotal": 280.0,
      "total": 280.0,
      "warnings": []
    },
    "readback_text": "Fortune Sunlite Oil 1L 2 packet — Total ₹280."
  }
  ```
- **Response** `200 OK` (Needs Clarification):
  ```json
  {
    "status": "needs_clarification",
    "clarifications": [
      {
        "raw_text": "oil",
        "quantity": 1.0,
        "question": "Which oil?",
        "candidates": [...],
        "speech_text": "Kaun sa oil? Fortune ya Sunflower?"
      }
    ],
    "partial_matched_items": []
  }
  ```

### `POST /api/v1/voice/feedback`
Records merchant's selection when a product was ambiguous, saving/updating a `ProductSynonym`.
- **Request**: `{"spoken_text": "fortune tel", "chosen_product_id": 42}`
- **Response** `200 OK`: `{"status": "success", "message": "Learned synonym...", "evidence_count": 3}`

---

## 5. AI Understanding & Assistant (`/api/v1/ai`, `/api/v1/assistant`, `/api/v1/alerts`)

### `POST /api/v1/ai/understand`
Converts transcript into structured JSON intent and entities without mutating database records or resolving catalog IDs.
- **Request**: `{"transcript": "2 kg chini aur 1 packet surf excel"}`
- **Response** `200 OK`: Returns structured parsed intent object.

### `POST /api/v1/assistant/query`
Natural language business assistant endpoint answering sales, inventory, and Khata questions strictly from local database queries (sales, bills, top products, low stock, udhaar) in Marathi, Hindi, or English.
- **Request**:
  ```json
  {
    "question": "Aaj kiti sale zali?",
    "language": "mr-IN"
  }
  ```
  *(Note: `language` is optional — accepted formats: `"mr-IN"`, `"hi-IN"`, `"en-IN"`, `"mr"`, `"hi"`, `"en"`. If omitted, language auto-detects from question markers or store preference).*
- **Response** `200 OK`:
  ```json
  {
    "answer_text": "आज तुमच्या दुकानात एकूण ₹308.00 ची विक्री झाली आहे (2 बिल्स).",
    "data_used": {
      "query_type": "sales_today",
      "result": {
        "total_revenue": 308.0,
        "txn_count": 2,
        "time_range": "today"
      }
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: `{"error": {"code": "VALIDATION_ERROR", "message": "question parameter is required."}}`


### `GET /api/v1/alerts`
Surfaces in-app low-stock items and pending Udhaar customer balances for active store dashboard.
- **Response** `200 OK`:
  ```json
  {
    "low_stock_alerts": [
      { "product_id": 5, "name": "Tata Salt 1kg", "quantity_on_hand": 2.0, "low_stock_threshold": 5.0, "unit": "packet" }
    ],
    "udhaar_alerts": [
      { "customer_id": 1, "name": "Ramesh", "phone": "9876543210", "outstanding_balance": 350.0 }
    ],
    "total_alerts": 2
  }
  ```

---

## 6. Billing (`/api/v1/billing`)

### `POST /api/v1/billing/create`
Creates or merges a draft bill from explicit product IDs and quantities (manual counter input).
- **Request**:
  ```json
  {
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 5, "quantity": 1}
    ],
    "customer_id": 1,
    "draft_bill_id": "optional-existing-draft-id"
  }
  ```
- **Response** `201 Created`: Returns draft bill structure and `readback_text`.

### `POST /api/v1/billing/confirm`
Finalizes a draft bill into an immutable `Transaction`, deducts stock atomically, and records `KhataEntry` if payment status is `'udhaar'`.
- **Request**:
  ```json
  {
    "draft_bill_id": "xyz789",
    "payment_status": "paid",
    "customer_id": null,
    "idempotency_key": "unique-client-key-123"
  }
  ```
- **Response** `200 OK`: Returns transaction object with `txn_id` and `invoice_number`.
- **Errors**:
  - `400` `CUSTOMER_REQUIRED` (if payment_status is `'udhaar'` and customer_id is missing)
  - `404` `DRAFT_BILL_NOT_FOUND`
  - `422` `INSUFFICIENT_STOCK` (with item name and available stock)

### `DELETE /api/v1/billing/<draft_bill_id>`
Voids an active draft bill before confirmation.
- **Response** `200 OK` or `404 DRAFT_BILL_NOT_FOUND`.

---

## 7. Products Catalog (`/api/v1/products`)

### `GET /api/v1/products`
Lists all active products for the authenticated owner's active store.
- **Response** `200 OK`: Array of product objects with pricing, categorization, SKU/barcode, and current inventory levels.

### `POST /api/v1/products` *(Owner only)*
Creates a new product with automated `normalized_name` computation and creates its initial `Inventory` record.
- **Request**:
  ```json
  {
    "name": "Fortune Sunlite Oil 1L",
    "unit": "packet",
    "price": 140.0,
    "category": "Cooking Essentials",
    "brand": "Fortune",
    "cost_price": 125.0,
    "sku": "FORT-1L",
    "barcode": "8901234567890",
    "quantity_on_hand": 50,
    "low_stock_threshold": 10
  }
  ```
- **Response** `201 Created`.

### `PATCH /api/v1/products/<int:product_id>` *(Owner only)*
Updates product details (name, price, cost_price, unit, category, brand, sku, barcode).
- **Response** `200 OK`.

### `DELETE /api/v1/products/<int:product_id>` *(Owner only)*
Soft-deletes a product (`is_active = False`).
- **Response** `200 OK`: `{"message": "Product deleted successfully."}`

### `GET /api/v1/products/search?q=<term>`
Live autocomplete search across product names, categories, barcodes, and SKUs.
- **Response** `200 OK`: Array of matching products.

### `GET /api/v1/products/stats`
Returns inventory summary metrics for the active store:
- `total_products`: Total active products count.
- `low_stock_count`: Count of items needing reorder.
- `out_of_stock_count`: Count of items with 0 or negative stock.
- `total_inventory_value`: Total valuation (`Σ quantity × cost_price/price`).

---

## 8. CSV Catalog Import (`/api/v1/products/import`)

### `POST /api/v1/products/import/preview` *(Owner only)*
Validates an uploaded CSV file and returns a preview of valid and invalid rows before importing.
- **Request** (multipart/form-data): `file`: `.csv` file.
- **Response** `200 OK`:
  ```json
  {
    "total_rows": 25,
    "valid_count": 25,
    "invalid_count": 0,
    "preview": [...],
    "errors": []
  }
  ```

### `POST /api/v1/products/import/confirm` *(Owner only)*
Commits validated rows into `Product` and `Inventory` tables and logs initial `STOCK_IN` movements.
- **Request**: JSON array of validated product items from preview.
- **Response** `201 Created`: `{"message": "Products imported successfully", "imported_count": 25}`.

---

## 9. Inventory Stock Tracking (`/api/v1/inventory`)

### `GET /api/v1/inventory`
Returns all active store products with live stock levels (`quantity_on_hand`, `low_stock_threshold`, `is_low_stock`, `stock_status`).
- **Response** `200 OK`.

### `PATCH /api/v1/inventory/<int:product_id>` *(Owner only)*
Manual stock correction. Updates `quantity_on_hand`, records an `InventoryAdjustment`, and logs an `ADJUSTMENT` movement in `InventoryMovement`.
- **Request**: `{"quantity_delta": -5.0, "reason": "Expired/damaged goods"}`
- **Response** `200 OK`: `{"product_id": 1, "quantity_on_hand": 45.0}`

### `GET /api/v1/inventory/<int:product_id>/history`
Returns chronological `InventoryMovement` audit records for the product.
- **Response** `200 OK`: Array of movement logs (`movement_type`, `previous_stock`, `new_stock`, `created_at`).

---

## 10. Customers & Khata Ledger (`/api/v1/customers`)

### `GET /api/v1/customers`
Lists all customers in the active store along with dynamically computed net Udhaar balances.
- **Response** `200 OK`: Array of `{customer_id, name, phone, balance}`.

### `POST /api/v1/customers`
Creates a customer profile. Checks for potential duplicate names or phone numbers and returns warnings if found.
- **Request**: `{"name": "Anil K", "phone": "9876500000"}`
- **Response** `201 Created`: Returns customer object and any `possible_duplicates`.

### `GET /api/v1/customers/<int:customer_id>/khata`
Fetches complete chronological credit and payment ledger entries for a customer.
- **Response** `200 OK`:
  ```json
  {
    "customer": { "customer_id": 1, "name": "Anil K", "phone": "9876500000" },
    "balance": 250.0,
    "entries": [
      { "entry_id": 1, "type": "credit", "amount": 500.0, "created_at": "..." },
      { "entry_id": 2, "type": "payment", "amount": 250.0, "created_at": "..." }
    ]
  }
  ```

---

## 11. Payments — Khata Settlement (`/api/v1/payments`)

### `POST /api/v1/payments`
Records a customer payment against outstanding Udhaar balance. Idempotent.
- **Request**:
  ```json
  {
    "customer_id": 1,
    "amount": 250.0,
    "idempotency_key": "pay-2026-10-04-001"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "message": "Payment recorded successfully.",
    "entry_id": 12,
    "customer_id": 1,
    "amount_paid": 250.0,
    "new_balance": 0.0
  }
  ```

---

## 12. Sales Analytics (`/api/v1/sales`)

### `GET /api/v1/sales/summary?range=today|week|custom` *(Owner only)*
Aggregated sales metrics for the specified time window.
- **Response** `200 OK`:
  ```json
  {
    "range": "today",
    "total_revenue": 1450.0,
    "txn_count": 8,
    "avg_order_value": 181.25,
    "outstanding_udhaar_total": 650.0
  }
  ```

### `GET /api/v1/sales/history?limit=50`
Returns chronological non-voided transaction list for the active store.
- **Response** `200 OK`: Array of transactions with invoice numbers, customer names, item counts, totals, and payment statuses.

---

## 13. Receipts & Invoices (`/api/v1/receipts`)

### `GET /api/v1/receipts/<int:txn_id>/view`
Renders a clean, thermal-printable HTML receipt document for an invoice.
- **Response** `200 OK` (HTML response).

### `POST /api/v1/receipts/generate`
Generates receipt data or dispatches SMS/WhatsApp receipt via Twilio integration if configured.
- **Request**: `{"txn_id": 101, "phone": "9876543210", "channel": "whatsapp"}`
- **Response** `200 OK`.

---

## 14. System & PWA Endpoints

### `GET /health`
System liveness and health verification endpoint.
- **Response** `200 OK`:
  ```json
  {
    "service": "Vyapar Saarthi AI API",
    "status": "healthy",
    "version": "1.0.0"
  }
  ```

### `GET /manifest.json`
PWA web application manifest (standalone mode, theme colors, icons).

### `GET /sw.js`
Network-first service worker JavaScript enabling offline cache fallback.
