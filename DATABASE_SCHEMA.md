# DATABASE_SCHEMA.md — Database Models & Schema Specification

---

## 1. Entity-Relationship Overview

```
 +------------------+   store_id FK   +-------------------+  store_id FK   +--------------------+
 |      users       | --------------> |      stores       | <------------- |      products      |
 +------------------+                 +-------------------+                +--------------------+
 | PK  user_id      |                 | PK  store_id      |                | PK  product_id     |
 | FK  store_id     |                 |     name          |                | FK  store_id       |
 |     role         |                 |     owner_user_id |                |     name           |
 |     name         |                 |     address       |                |     normalized_name|
 |     phone        |                 |     language_pref |                |     price          |
 |     password_hash|                 +-------------------+                |     cost_price     |
 +------------------+                                                      |     unit           |
          |                                                                |     category       |
          | user_id FK                                                     |     brand          |
          v                                                                |     sku / barcode  |
 +------------------+   customer_id FK +-------------------+              |     is_active      |
 |  khata_entries   | <--------------- |    customers      |              +--------------------+
 +------------------+                  +-------------------+                       |
 | PK  entry_id     |                  | PK  customer_id   |                       | product_id FK
 | FK  customer_id  |                  | FK  store_id      |                       v
 | FK  store_id     |                  |     name          |              +--------------------+
 | FK  txn_id       |                  |     phone         |              |     inventory      |
 |     amount       |                  +-------------------+              +--------------------+
 |     type         |                           |                         | PK  product_id     |
 | FK  recorded_by_ |                  customer_id FK                    |     qty_on_hand    |
 |     user_id      |                           v                        |     low_stk_thresh |
 +------------------+                  +-------------------+              +--------------------+
                                        |   transactions    |
                                        +-------------------+              +--------------------+
                                        | PK  txn_id        |              | inventory_movements|
                                        | FK  store_id      |              +--------------------+
                                        | FK  customer_id   |              | PK  movement_id    |
                                        | FK  created_by_   |              | FK  product_id     |
                                        |     user_id       |              |     movement_type  |
                                        |     total         |              |     previous_stock |
                                        |     payment_status|              |     new_stock      |
                                        |     invoice_number|              +--------------------+
                                        |     voided_at     |
                                        +-------------------+
                                                 |
                                                 | txn_id FK
                                                 v
                                        +-------------------+
                                        | transaction_items |
                                        +-------------------+
                                        | PK  txn_item_id   |
                                        | FK  txn_id        |
                                        | FK  product_id    |
                                        |     quantity      |
                                        |     unit_price    |
                                        |     line_total    |
                                        +-------------------+
```

---

## 2. Comprehensive Table Specifications

### 1. `users` ([app/models/user.py](file:///d:/projectss/Vypaar%20sarthi/app/models/user.py))
Merchant user accounts. Authentication is phone-based (not email/username).

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `user_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | |
| `role` | Enum | Not Null | — | `'owner'` or `'helper'` only |
| `name` | String(150) | Not Null | — | Display name |
| `phone` | String(20) | Not Null | — | Login identifier |
| `password_hash` | String(255) | Not Null | — | Scrypt via werkzeug |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | Auto-updates on change |

**Unique Constraint**: `(store_id, phone)` — phone number must be unique per store, not globally.

---

### 2. `stores` ([app/models/store.py](file:///d:/projectss/Vypaar%20sarthi/app/models/store.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `store_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `name` | String(150) | Not Null | — | Business name |
| `owner_user_id` | BigInteger | **FK** → `users.user_id` (deferred, `use_alter=True`), Nullable | — | Set after owner creation |
| `address` | String(255) | Nullable | — | |
| `language_pref` | String(20) | Not Null | `'hi-en'` | Voice language preference |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Relationships**: Has `users`, `products`, `customers`, `transactions`, `voice_sessions`.

> **Note**: `owner_user_id` uses `use_alter=True` to avoid circular FK dependency during table creation (Store references User, User references Store).

---

### 3. `products` ([app/models/product.py](file:///d:/projectss/Vypaar%20sarthi/app/models/product.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | |
| `name` | String(150) | Not Null | — | Raw display name |
| `normalized_name` | String(150) | Not Null | Auto-computed | Lowercase, stripped of special chars, unidecoded |
| `unit` | String(20) | Not Null | — | `'kg'`, `'g'`, `'l'`, `'ml'`, `'piece'`, `'packet'` |
| `price` | Numeric(10,2) | Not Null | — | **Selling price** (primary) |
| `cost_price` | Numeric(10,2) | Nullable | — | Purchase/cost price |
| `category` | String(100) | Nullable | — | |
| `brand` | String(100) | Nullable | — | |
| `sku` | String(100) | Nullable | — | |
| `barcode` | String(100) | Nullable | — | |
| `image_url` | String(500) | Nullable | — | |
| `is_active` | Boolean | Not Null | `True` | Soft-delete flag |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Indexes**: `(store_id, normalized_name)`, `(store_id, category)`  
**Unique Constraint**: `(store_id, sku)` — SKU unique per store.  
**Auto `__init__`**: `normalized_name` is computed automatically from `name` using `unidecode` + regex cleanup.

---

### 4. `product_synonyms` ([app/models/product_synonym.py](file:///d:/projectss/Vypaar%20sarthi/app/models/product_synonym.py))
Regional and merchant-learned alternate product name terms.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `synonym_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Nullable | — | Null = global synonym |
| `term` | String(100) | Not Null | — | Spoken or alternate term |
| `maps_to_category` | String(100) | Nullable | — | Maps to a product category |
| `maps_to_product_id` | BigInteger | **FK** → `products.product_id`, Nullable | — | Maps to specific product |
| `language` | String(10) | Nullable | — | e.g. `'hi'`, `'en'` |
| `evidence_count` | Integer | Not Null | `1` | Incremented per merchant confirmation |
| `last_confirmed_at` | DateTime | Nullable | UTC Now | |
| `is_auto_learned` | Boolean | Not Null | `False` | True if learned from voice feedback |

**Index**: `(store_id, term)`

---

### 5. `inventory` ([app/models/inventory.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory.py))
One-to-one with `Product`. Holds current live stock levels.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | BigInteger (Integer in SQLite) | **PK**, **FK** → `products.product_id` | — | Shared PK = enforces 1:1 |
| `quantity_on_hand` | Numeric(10,3) | Not Null | `0` | Current available stock |
| `low_stock_threshold` | Numeric(10,3) | Not Null | `0` | Alert trigger level |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Computed Properties**:
- `is_low_stock` → `True` if `quantity_on_hand <= low_stock_threshold`
- `stock_status` → `"out_of_stock"` (qty ≤ 0), `"low_stock"` (qty ≤ threshold), `"in_stock"`

---

### 6. `inventory_movements` ([app/models/inventory_movement.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory_movement.py))
Immutable audit log of every stock quantity change.

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `movement_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id` | — | |
| `product_id` | BigInteger | **FK** → `products.product_id` | — | |
| `movement_type` | String(50) | Not Null | — | `STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`, `SALE`, `RETURN` |
| `quantity` | Numeric(10,3) | Not Null | — | |
| `previous_stock` | Numeric(10,3) | Not Null | — | Stock before this event |
| `new_stock` | Numeric(10,3) | Not Null | — | Stock after this event |
| `reason` | String(255) | Nullable | — | |
| `created_at` | DateTime | Not Null | UTC Now | |

---

### 7. `inventory_adjustments` ([app/models/inventory_adjustment.py](file:///d:/projectss/Vypaar%20sarthi/app/models/inventory_adjustment.py))
Owner-only manual stock correction records (separate from movement log).

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `adjustment_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `product_id` | BigInteger | **FK** → `products.product_id` | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id` | — | |
| `quantity_delta` | Numeric(10,3) | Not Null | — | Positive = add, negative = remove |
| `reason` | String(255) | Not Null | — | |
| `adjusted_by_user_id` | BigInteger | **FK** → `users.user_id` | — | Must be `'owner'` |
| `created_at` | DateTime | Not Null | UTC Now | |

---

### 8. `customers` ([app/models/customer.py](file:///d:/projectss/Vypaar%20sarthi/app/models/customer.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `customer_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | |
| `name` | String(150) | Not Null | — | |
| `phone` | String(20) | Nullable | — | Not required |
| `created_at` | DateTime | Not Null | UTC Now | |
| `updated_at` | DateTime | Not Null | UTC Now | |

**Indexes**: `(store_id, name)`, `(store_id, phone)`  
> **Note**: There is **no `credit_limit` or `current_balance` column**. Customer outstanding balance is computed dynamically by summing `KhataEntry` records via `KhataEngine.get_customer_balance(customer_id)`.

---

### 9. `khata_entries` ([app/models/khata.py](file:///d:/projectss/Vypaar%20sarthi/app/models/khata.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `entry_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `customer_id` | BigInteger | **FK** → `customers.customer_id`, Not Null | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | |
| `txn_id` | BigInteger | **FK** → `transactions.txn_id`, Nullable | — | Linked invoice (if credit via bill) |
| `amount` | Numeric(10,2) | Not Null | — | |
| `type` | Enum | Not Null | — | `'credit'` (Udhaar) or `'payment'` (Jama) |
| `recorded_by_user_id` | BigInteger | **FK** → `users.user_id`, Not Null | — | Who recorded this entry |
| `created_at` | DateTime | Not Null | UTC Now | |

**Index**: `(customer_id, created_at)`

---

### 10. `transactions` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `txn_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `store_id` | BigInteger | **FK** → `stores.store_id`, Not Null | — | |
| `customer_id` | BigInteger | **FK** → `customers.customer_id`, Nullable | — | Walk-in customer = null |
| `total` | Numeric(10,2) | Not Null | — | Final transaction amount |
| `payment_status` | Enum | Not Null | — | `'paid'` or `'udhaar'` |
| `invoice_number` | String(50) | Not Null | — | |
| `created_by_user_id` | BigInteger | **FK** → `users.user_id`, Not Null | — | |
| `voided_at` | DateTime | Nullable | — | Set when voided |
| `void_reason` | String(255) | Nullable | — | |
| `created_at` | DateTime | Not Null | UTC Now | |

**Unique Constraint**: `(store_id, invoice_number)`  
**Relationships**: `items` (TransactionItem), `adjustments` (TransactionAdjustment), `creator` (User)

---

### 11. `transaction_items` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))

| Column | Type | Constraints | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `txn_item_id` | BigInteger (Integer in SQLite) | **PK**, AutoIncrement | — | |
| `txn_id` | BigInteger | **FK** → `transactions.txn_id`, Not Null | — | |
| `product_id` | BigInteger | **FK** → `products.product_id`, Not Null | — | |
| `quantity` | Numeric(10,3) | Not Null | — | Supports fractional quantities |
| `unit_price` | Numeric(10,2) | Not Null | — | Price snapshot at time of sale |
| `line_total` | Numeric(10,2) | Not Null | — | `quantity × unit_price` |

---

### 12. `transaction_adjustments` ([app/models/transaction.py](file:///d:/projectss/Vypaar%20sarthi/app/models/transaction.py))
Post-confirmation corrections to completed transactions.

| Column | Type | Constraints | Notes |
| :--- | :--- | :--- | :--- |
| `adjustment_id` | BigInteger (Integer in SQLite) | **PK** | |
| `original_txn_id` | BigInteger | **FK** → `transactions.txn_id` | |
| `adjustment_type` | Enum | Not Null | `'void'`, `'item_correction'`, `'refund'` |
| `description` | String(255) | Not Null | |
| `amount_delta` | Numeric(10,2) | Not Null | Positive = charge more, negative = refund |
| `adjusted_by_user_id` | BigInteger | **FK** → `users.user_id` | |
| `created_at` | DateTime | Not Null | |

---

### 13. `draft_bills` ([app/models/draft_bill.py](file:///d:/projectss/Vypaar%20sarthi/app/models/draft_bill.py))

| Column | Type | Notes |
| :--- | :--- | :--- |
| `draft_bill_id` | String(64) | **PK** — UUID string, not auto-integer |
| `store_id` | Integer | FK → `stores.store_id` |
| `customer_id` | Integer | FK → `customers.customer_id`, Nullable |
| `line_items_json` | Text | JSON-serialized list of line item dicts |
| `subtotal` | Numeric(10,2) | Pre-discount total |
| `total` | Numeric(10,2) | Final total |
| `warnings_json` | Text | Nullable — JSON list of warning strings |
| `created_at` | DateTime | |

---

### 14. `billing_idempotency` ([app/models/draft_bill.py](file:///d:/projectss/Vypaar%20sarthi/app/models/draft_bill.py))
Prevents duplicate `confirm` submissions.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | Integer | **PK** |
| `cache_key` | String(128) | Unique, Indexed — the merchant's `idempotency_key` |
| `response_json` | Text | Serialized response for replay |
| `created_at` | DateTime | |

---

### 15. `voice_sessions` ([app/models/voice_session.py](file:///d:/projectss/Vypaar%20sarthi/app/models/voice_session.py))

| Column | Type | Notes |
| :--- | :--- | :--- |
| `session_id` | String(36) | **PK** — UUID string |
| `store_id` | BigInteger | FK → `stores.store_id` |
| `user_id` | BigInteger | FK → `users.user_id` |
| `transcript` | Text | Full STT output |
| `resolved_intent` | String(50) | Nullable — final classified intent |
| `confidence_score` | Numeric(4,3) | Nullable — STT confidence |
| `needed_clarification` | Boolean | True if product match was ambiguous |
| `linked_txn_id` | BigInteger | FK → `transactions.txn_id`, Nullable |
| `created_at` | DateTime | |
