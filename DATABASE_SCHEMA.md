# DATABASE_SCHEMA.md — Database Models & Schema Specification

> **Current Working Condition**: Fully maps all 16 SQLAlchemy models defined in `app/models/`.

---

## 1. Entity-Relationship Overview

```
       +-------------------+  owner_id FK  +-------------------+
       |       users       | <------------ |   owner_stores    |
       +-------------------+               +-------------------+
       | PK  user_id       |               | PK  id            |
       | FK  store_id      | --+           | FK  owner_id      |
       |     role          |   |           | FK  store_id      |
       |     name          |   |           |     is_primary    |
       |     phone         |   |           +-------------------+
       |     password_hash |   |                     |
       +-------------------+   |                     | store_id FK
          |                    |                     v
          | owner_user_id FK   |           +-------------------+
          +--------------------+---->      |      stores       |
                                           +-------------------+
                                           | PK  store_id      |
                                           |     name          |
                                           | FK  owner_user_id |
                                           |     phone         |
                                           |     gstin         |
                                           |     address       |
                                           |     language_pref |
                                           |     is_active     |
                                           +-------------------+
                                            /     |         \
                               store_id FK /      |          \ store_id FK
                                          v       |           v
   +-------------------+  store_id FK  +-----+    |    +--------------------+
   |     customers     | <------------ |     |    |    |      products      |
   +-------------------+               +-----+    |    +--------------------+
   | PK  customer_id   |                          |    | PK  product_id     |
   | FK  store_id      |                          |    | FK  store_id       |
   |     name          |                          |    |     name           |
   |     phone         |                          |    |     normalized_name|
   +-------------------+                          |    |     unit           |
      |             |                             |    |     price          |
      | customer_id | customer_id                 |    |     cost_price     |
      | FK          | FK                          |    |     category       |
      v             v                             |    |     brand          |
   +-------------+ +--------------------+         |    |     sku / barcode  |
   |khata_entries| |    transactions    |         |    |     is_active      |
   +-------------+ +--------------------+         |    +--------------------+
   | PK entry_id | | PK  txn_id         |         |       |              |
   | FK cust_id  | | FK  store_id       |         |       |              | product_id FK
   | FK store_id | | FK  customer_id    |         |       |              v
   | FK txn_id   | |     total          |         |       |     +--------------------+
   |    amount   | |     payment_status |         |       |     |     inventory      |
   |    type     | |     invoice_number |         |       |     +--------------------+
   | FK rec_user | | FK  created_by_user|         |       |     | PK product_id (1:1)|
   +-------------+ |     voided_at      |         |       |     |    quantity_on_hand|
                   +--------------------+         |       |     |    low_stk_thresh  |
                             |                    |       |     +--------------------+
                             | txn_id FK          |       |
                             v                    |       +--------+
                   +--------------------+         |                |
                   | transaction_items  |         |                |
                   +--------------------+         |                v
                   | PK  txn_item_id    |         |     +----------------------+
                   | FK  txn_id         |         |     | inventory_movements  |
                   | FK  product_id     |         |     +----------------------+
                   |     quantity       |         |     | PK movement_id       |
                   |     unit_price     |         |     | FK store_id          |
                   |     line_total     |         |     | FK product_id        |
                   +--------------------+         |     |    movement_type     |
                                                  |     |    quantity          |
     +--------------------------------------------+     |    prev/new_stock    |
     |                                                  +----------------------+
     v
+-----------------------+   +----------------------+   +----------------------+
|     draft_bills       |   | billing_idempotency  |   |    voice_sessions    |
+-----------------------+   +----------------------+   +----------------------+
| PK  draft_bill_id     |   | PK  id               |   | PK session_id (UUID) |
| FK  store_id          |   |     cache_key (uniq) |   | FK store_id          |
| FK  customer_id       |   |     response_json    |   | FK user_id           |
|     line_items_json   |   |     created_at       |   |    transcript        |
|     subtotal / total  |   +----------------------+   |    resolved_intent   |
|     warnings_json     |                              |    confidence_score  |
+-----------------------+                              | FK linked_txn_id     |
                                                       +----------------------+
```

---

## 2. Comprehensive Table Specifications (All 16 Models)

### 1. `users` ([app/models/user.py](file:///d:/projectss/Vypaar%20sarthi/app/models/user.py))
Store merchant and helper accounts. Authentication uses phone numbers.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `user_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | Home store |
| `role` | Enum (`'owner'`, `'helper'`) | Not Null | — | Role-based permissions |
| `name` | String(150) | Not Null | — | Merchant name |
| `phone` | String(20) | Not Null | — | Login identifier |
| `password_hash` | String(255) | Not Null | — | Scrypt via werkzeug |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | Auto-updates on edit |

**Unique Constraint**: `(store_id, phone)`  
**Property**: `accessible_store_ids` returns all stores owned via `owner_stores` or assigned `store_id`.

---

### 2. `stores` ([app/models/store.py](file:///d:/projectss/Vypaar%20sarthi/app/models/store.py))
Retail store and outlet entities.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `store_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `name` | String(150) | Not Null | — | Shop name |
| `owner_user_id` | BigInteger | **FK** → `users.user_id` (`use_alter=True`), Nullable | — | Owner user link |
| `phone` | String(20) | Nullable | — | Shop contact number |
| `gstin` | String(20) | Nullable | — | GST identification number |
| `address` | String(255) | Nullable | — | Physical store location |
| `language_pref` | String(20) | Not Null | `'hi-en'` | Spoken language preference |
| `is_active` | Boolean | Not Null | `True` | Soft-delete status flag |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | |

---

### 3. `owner_stores` ([app/models/owner_store.py](file:///d:/projectss/Vypaar%20sarthi/app/models/owner_store.py))
Junction table enabling multi-store ownership per owner account.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `owner_id` | BigInteger | **FK** → `users.user_id` (Cascade), Not Null | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id` (Cascade), Not Null | — | |
| `is_primary` | Boolean | Not Null | `False` | Primary store flag |
| `added_at` | DateTime | Not Null | UTC Now | |

**Unique Constraint**: `(owner_id, store_id)`  
**Index**: `(owner_id)`

---

### 4. `products` ([app/models/product.py](file:///d:/projectss/Vypaar%20sarthi/app/models/product.py))
Store product catalog.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | Store isolation |
| `name` | String(150) | Not Null | — | Display product name |
| `normalized_name` | String(150) | Not Null | Auto-computed | ASCII lowercased token for matching |
| `unit` | String(20) | Not Null | — | `'packet'`, `'kg'`, `'g'`, `'l'`, `'piece'` |
| `price` | Numeric(10,2) | Not Null | — | Selling price |
| `cost_price` | Numeric(10,2) | Nullable | — | Purchase cost |
| `category` | String(100) | Nullable | — | Product category |
| `brand` | String(100) | Nullable | — | Brand name |
| `sku` | String(100) | Nullable | — | Stock keeping unit |
| `barcode` | String(100) | Nullable | — | Scannable barcode |
| `image_url` | String(500) | Nullable | — | Product image |
| `is_active` | Boolean | Not Null | `True` | Soft-delete flag |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Indexes**: `(store_id, normalized_name)`, `(store_id, category)`  
**Unique Constraint**: `(store_id, sku)`

---

### 5. `product_synonyms` ([app/models/product_synonym.py](file:///d:/projectss/Vypaar%20sarthi/app/models/product_synonym.py))
Regional and merchant-learned phonetic alternate terms.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `synonym_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Nullable | — | Null = global synonym |
| `term` | String(100) | Not Null | — | Spoken or alternate term |
| `maps_to_category` | String(100) | Nullable | — | Category fallback mapping |
| `maps_to_product_id` | BigInteger | **FK** → `products.product_id`, Nullable | — | Specific product mapping |
| `language` | String(10) | Nullable | — | `'hi'`, `'mr'`, `'en'` |
| `evidence_count` | Integer | Not Null | `1` | Increments upon merchant confirmation |
| `last_confirmed_at` | DateTime | Nullable | UTC Now | |
| `is_auto_learned` | Boolean | Not Null | `False` | True if added via voice feedback |

**Index**: `(store_id, term)`

---

### 6. `inventory` ([app/models/inventory.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory.py))
One-to-one with `Product`, holding live available quantities.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | BigInteger (Integer in SQLite) | **PK**, **FK** → `products.product_id` | — | Shared PK enforces 1:1 relation |
| `quantity_on_hand` | Numeric(10,3) | Not Null | `0` | Live stock quantity |
| `low_stock_threshold` | Numeric(10,3) | Not Null | `0` | Reorder alert threshold |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Computed Properties**:
- `is_low_stock` → `quantity_on_hand <= low_stock_threshold`
- `stock_status` → `"out_of_stock"` (≤0), `"low_stock"`, `"in_stock"`

---

### 7. `inventory_movements` ([app/models/inventory_movement.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory_movement.py))
Immutable chronological audit log of all stock changes.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `movement_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `store_id` | BigInteger | **FK** → `stores.store_id` | |
| `product_id` | BigInteger | **FK** → `products.product_id` | |
| `movement_type` | String(50) | Not Null | `STOCK_IN`, `STOCK_OUT`, `SALE`, `ADJUSTMENT`, `RETURN` |
| `quantity` | Numeric(10,3) | Not Null | Quantity changed |
| `previous_stock` | Numeric(10,3) | Not Null | Stock before movement |
| `new_stock` | Numeric(10,3) | Not Null | Stock after movement |
| `reason` | String(255) | Nullable | Description / note |
| `created_at` | DateTime | Not Null | UTC Now |

---

### 8. `inventory_adjustments` ([app/models/inventory_adjustment.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory_adjustment.py))
Owner-only manual stock correction records.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `adjustment_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `product_id` | BigInteger | **FK** → `products.product_id` | |
| `store_id` | BigInteger | **FK** → `stores.store_id` | |
| `quantity_delta` | Numeric(10,3) | Not Null | Positive to add, negative to deduct |
| `reason` | String(255) | Not Null | Required explanation |
| `adjusted_by_user_id` | BigInteger | **FK** → `users.user_id` | Must have role `'owner'` |
| `created_at` | DateTime | Not Null | UTC Now |

---

### 9. `customers` ([app/models/customer.py](file:///d:/projectss/Vypaar%20sarthi/app/models/customer.py))
Customer directory for Khata and billing.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `customer_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | |
| `name` | String(150) | Not Null | Customer name |
| `phone` | String(20) | Nullable | Optional contact number |
| `created_at` | DateTime | Not Null | UTC Now |
| `updated_at` | DateTime | Not Null | UTC Now |

**Indexes**: `(store_id, name)`, `(store_id, phone)`  
> **Balance Calculation**: Outstanding Udhaar balance is calculated dynamically via `KhataEngine.get_customer_balance(customer_id)`.

---

### 10. `khata_entries` ([app/models/khata.py](file:///d:/projectss/Vypaar%20sarthi/app/models/khata.py))
Udhaar and payment ledger entries.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `entry_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `customer_id` | BigInteger | **FK** → `customers.customer_id`, Not Null | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | |
| `txn_id` | BigInteger | **FK** → `transactions.txn_id`, Nullable | Linked invoice if from bill |
| `amount` | Numeric(10,2) | Not Null | Transaction value |
| `type` | Enum (`'credit'`, `'payment'`) | Not Null | `'credit'` (Udhaar) / `'payment'` (Jama) |
| `recorded_by_user_id` | BigInteger | **FK** → `users.user_id`, Not Null | User who logged entry |
| `created_at` | DateTime | Not Null | UTC Now |

**Index**: `(customer_id, created_at)`

---

### 11. `transactions` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))
Finalized, committed sales transactions.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `txn_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | |
| `customer_id` | BigInteger | **FK** → `customers.customer_id`, Nullable | Null for walk-in retail |
| `total` | Numeric(10,2) | Not Null | Total transaction amount |
| `payment_status` | Enum (`'paid'`, `'udhaar'`) | Not Null | |
| `invoice_number` | String(50) | Not Null | Human-readable bill number |
| `created_by_user_id` | BigInteger | **FK** → `users.user_id`, Not Null | Cashier/staff user |
| `voided_at` | DateTime | Nullable | Timestamp if voided |
| `void_reason` | String(255) | Nullable | Reason for void |
| `created_at` | DateTime | Not Null | UTC Now |

**Unique Constraint**: `(store_id, invoice_number)`

---

### 12. `transaction_items` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))
Itemized rows within a transaction.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `txn_item_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `txn_id` | BigInteger | **FK** → `transactions.txn_id`, Not Null | |
| `product_id` | BigInteger | **FK** → `products.product_id`, Not Null | |
| `quantity` | Numeric(10,3) | Not Null | Fractional quantities supported |
| `unit_price` | Numeric(10,2) | Not Null | Historical price snapshot |
| `line_total` | Numeric(10,2) | Not Null | `quantity × unit_price` |

---

### 13. `transaction_adjustments` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))
Post-confirmation corrections to transactions.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `adjustment_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | |
| `original_txn_id` | BigInteger | **FK** → `transactions.txn_id`, Not Null | |
| `adjustment_type` | Enum (`'void'`, `'item_correction'`, `'refund'`) | Not Null | |
| `description` | String(255) | Not Null | Reason |
| `amount_delta` | Numeric(10,2) | Not Null | Net monetary change |
| `adjusted_by_user_id` | BigInteger | **FK** → `users.user_id`, Not Null | |
| `created_at` | DateTime | Not Null | UTC Now |

---

### 14. `draft_bills` ([app/models/draft_bill.py](file:///d:/projectss/Vypaar%20sarthi/app/models/draft_bill.py))
Temporary staged bills created during voice billing or counter entry before commit.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `draft_bill_id` | String(64) | **PK** | UUID string identifier |
| `store_id` | Integer | **FK** → `stores.store_id`, Not Null | |
| `customer_id` | Integer | **FK** → `customers.customer_id`, Nullable | |
| `line_items_json` | Text | Not Null | Serialized JSON list of item dicts |
| `subtotal` | Numeric(10,2) | Not Null | Pre-discount total |
| `total` | Numeric(10,2) | Not Null | Final amount |
| `warnings_json` | Text | Nullable | Serialized warning messages |
| `created_at` | DateTime | Nullable | UTC Now |

---

### 15. `billing_idempotency` ([app/models/draft_bill.py](file:///d:/projectss/Vypaar%20sarthi/app/models/draft_bill.py))
Prevents duplicate bill confirmation calls.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `id` | Integer | **PK**, AutoIncrement | |
| `cache_key` | String(128) | Not Null, Unique, Indexed | Client idempotency key |
| `response_json` | Text | Not Null | Cached JSON replay response |
| `created_at` | DateTime | Nullable | UTC Now |

---

### 16. `voice_sessions` ([app/models/voice_session.py](file:///d:/projectss/Vypaar%20sarthi/app/models/voice_session.py))
Audio transcription and NLP intent audit logs.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `session_id` | String(36) | **PK** | UUID string identifier |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | |
| `user_id` | BigInteger | **FK** → `users.user_id`, Not Null | |
| `transcript` | Text | Not Null | Full STT output |
| `resolved_intent` | String(50) | Nullable | Final classified intent |
| `confidence_score` | Numeric(4,3) | Nullable | STT/NLP confidence (0.0 to 1.0) |
| `needed_clarification` | Boolean | Not Null | True if product match was ambiguous |
| `linked_txn_id` | BigInteger | **FK** → `transactions.txn_id`, Nullable | Final invoice link |
| `created_at` | DateTime | Not Null | UTC Now |
