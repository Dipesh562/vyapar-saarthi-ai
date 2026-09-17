# API_SPECIFICATION.md — REST API Endpoint Specification

---

## 1. Global API Conventions

### Base URL & Versioning
All application endpoints are under `/api/v1/` except `/health`, `/`, `/manifest.json`, and `/sw.js`.

### Authentication
- Session-based via `Flask-Login`.
- Login via `POST /api/v1/auth/login` (phone + password).
- Protected routes require a valid session cookie. Unauthorized access returns `401`.

### Role-Based Access Control
Some endpoints are restricted to `'owner'` role only:
- Manual inventory adjustments (`PATCH /api/v1/inventory/<product_id>`)
- Registering helper users (`POST /api/v1/auth/register_helper`)

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
Creates a store and links an owner user account. Calls `login_user()` immediately.
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
- **Response**: `201 Created`
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

### `POST /api/v1/auth/register_helper`
Owner-only. Registers a new helper for the owner's store.
- **Request**: `{"name": "Suresh", "phone": "9876540000", "password": "helper123"}`
- **Response**: `201 Created`

### `POST /api/v1/auth/login`
Phone-based login.
- **Request**: `{"phone": "9876543210", "password": "SecurePass123"}`
- **Response**: `200 OK`
  ```json
  {
    "message": "Logged in successfully.",
    "user": {
      "user_id": 1, "name": "Ramesh Sharma",
      "role": "owner", "store_id": 1
    }
  }
  ```

### `POST /api/v1/auth/logout`
Clears session. Returns `200 OK`.

### `GET /api/v1/auth/me`
Returns currently authenticated user and store info. Returns `200 OK`.

---

## 3. Voice Billing (`/api/v1/voice`)

### `POST /api/v1/voice/transcribe`
Accepts audio file or plain text for STT transcription and creates a `VoiceSession` record.
- **Request** (multipart/form-data):
  - `audio`: Binary audio file (WAV, WebM)
  - `transcript_text`: *(Optional)* Plain text override for testing
  - `language_hint`: *(Optional)* `"hi-IN"` or `"en-IN"`
  - `session_id`: *(Optional)* Reuse existing session UUID
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
End-to-end voice billing. Parses intent → matches products → creates/merges `DraftBill`.
- **Request**:
  ```json
  {
    "transcript": "Do packet Fortune Oil aur ek kilo Tata Namak",
    "session_id": "8a32f912-...",
    "draft_bill_id": "abc123"
  }
  ```
  > If `draft_bill_id` is provided, new items are **merged** into the existing draft (quantities aggregated per product), and the old draft is voided.

- **Response** `201 Created` (draft created):
  ```json
  {
    "session_id": "8a32f912-...",
    "status": "draft_created",
    "payment_status": "paid",
    "draft_bill": {
      "draft_bill_id": "xyz789",
      "line_items": [...],
      "subtotal": 308.0,
      "total": 308.0,
      "warnings": []
    },
    "readback_text": "Do packet Fortune Oil aur ek kilo Tata Namak — Total ₹308."
  }
  ```
- **Response** `200 OK` (needs clarification — ambiguous product):
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
- **Response** `200 OK` (routed query — not a billing action):
  ```json
  {
    "status": "query",
    "intent": "check_stock",
    "message": "Recognized intent: 'check_stock'. Please use the Assistant tab for business queries."
  }
  ```

### `POST /api/v1/voice/feedback`
Records merchant's choice when a product was ambiguous. Saves/updates a `ProductSynonym` record.
- **Request**: `{"spoken_text": "fortune tel", "chosen_product_id": 42}`
- **Response** `200 OK`: `{"status": "success", "message": "Learned synonym...", "evidence_count": 3}`

---

## 4. Billing (`/api/v1/billing`)

### `POST /api/v1/billing/create`
Creates a draft bill from explicit product IDs and quantities (manual, non-voice path).
- **Request**:
  ```json
  {
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 5, "quantity": 1}
    ],
    "customer_id": 1,
    "draft_bill_id": "existing-draft-uuid"
  }
  ```
  > If `draft_bill_id` is provided, merges with existing draft.
- **Response**: `201 Created` — returns full draft bill dict with `readback_text`.

### `POST /api/v1/billing/confirm`
Finalizes a draft bill into a committed `Transaction`. Deducts inventory atomically.
- **Request**:
  ```json
  {
    "draft_bill_id": "xyz789",
    "payment_status": "paid",
    "customer_id": 1,
    "idempotency_key": "unique-client-key-abc"
  }
  ```
  > `payment_status` must be `'paid'` or `'udhaar'`. If `'udhaar'`, `customer_id` is **required**.

- **Response** `200 OK`: Returns transaction details including `txn_id` and `invoice_number`.
- **Errors**:
  - `404` `DRAFT_BILL_NOT_FOUND`
  - `400` `CUSTOMER_REQUIRED` (udhaar without customer)
  - `422` `INSUFFICIENT_STOCK` with details on which product and how much is available

### `DELETE /api/v1/billing/<draft_bill_id>`
Voids a draft before confirmation.
- **Response** `200 OK` or `404 DRAFT_BILL_NOT_FOUND`.

---

## 5. Inventory (`/api/v1/inventory`)

### `GET /api/v1/inventory`
Returns all active products with current stock levels.
- **Response** `200 OK`: Array of `{product_id, name, quantity_on_hand, low_stock_threshold, is_low}`.

### `PATCH /api/v1/inventory/<product_id>` *(Owner only)*
Manual stock correction.
- **Request**: `{"quantity_delta": -5.0, "reason": "Spoilage — expired goods"}`
- **Response** `200 OK`: `{"product_id": 1, "quantity_on_hand": 45.0}`

### `GET /api/v1/inventory/<product_id>/history`
Returns the `InventoryMovement` log for a product.
- **Response** `200 OK`: Array of movement records with `movement_type`, `previous_stock`, `new_stock`.

---

## 6. Payments — Khata Collection (`/api/v1/payments`)

### `POST /api/v1/payments`
Records a customer payment against outstanding Udhaar balance. Idempotent.
- **Request**:
  ```json
  {
    "customer_id": 1,
    "amount": 500.0,
    "idempotency_key": "pay-2026-09-16-001"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "message": "Payment recorded successfully.",
    "entry_id": 12,
    "customer_id": 1,
    "amount_paid": 500.0,
    "new_balance": 250.0
  }
  ```
- **Errors**: `400 INVALID_AMOUNT`, `404 CUSTOMER_NOT_FOUND`

---

## 7. System Health

### `GET /health`
- **Response** `200 OK`: `{"status": "ok", "service": "Vyapar Saarthi AI"}` (approximately)
