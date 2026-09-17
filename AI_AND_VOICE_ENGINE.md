# AI_AND_VOICE_ENGINE.md — AI, NLP & Voice Processing Pipeline

---

## 1. Multi-Stage Voice Billing Pipeline

```
[Merchant Speaks into Mic / Types Text]
               |
               v
+-----------------------------------+
|   STT Transcription               |
|  (app/services/stt_client.py)     |
|                                   |
|  - Validates audio bytes          |
|  - Passes language hint (hi-IN)   |
|  - Returns transcript + confidence|
+-----------------------------------+
               |
    confidence < 0.60 → reject (LOW_CONFIDENCE_TRANSCRIPTION)
               |
               v
+-----------------------------------+
|  AI Intent & Entity Extraction    |
|(app/services/ai_orchestration.py) |
|                                   |
|  - Classifies intent              |
|  - Extracts items: name, qty, unit|
|  - Identifies customer_name       |
|  - Identifies payment_status      |
+-----------------------------------+
               |
     +---------+---------+
     |                   |
     v                   v
[Cart Intents]     [Query Intents]
(add_item, etc.)   (check_stock,
     |              business_query)
     |                   |
     v                   v
+---------------+  +------------------+
| Product       |  | Query Router     |
| Matching      |  | (local SQL vs    |
| Engine        |  |  Cloud LLM)      |
+---------------+  +------------------+
     |
     +-- Matched → add to matched_items
     |
     +-- Ambiguous → clarifications_needed[]
     |              (VoiceFeedbackService.
     |               build_clarification_speech_text)
     |
     +-- Not found → clarifications_needed[]
               |
               v
+-----------------------------------+
|  MerchantCartSession              |
|  (app/services/cart_session.py)   |
|                                   |
|  - Stores last matched item       |
|  - Stores last customer           |
|  - Resolves "aur do" / "add more" |
|    referential follow-up phrases  |
+-----------------------------------+
               |
               v
+-----------------------------------+
|  BillingEngine.create_draft_bill  |
|  (app/services/billing_engine.py) |
|                                   |
|  - Creates / merges DraftBill     |
|  - Returns subtotal, total,       |
|    line_items, warnings           |
+-----------------------------------+
               |
               v
+-----------------------------------+
|  VoiceFeedbackService.            |
|  build_readback_text(draft_bill)  |
|                                   |
|  Generates Hinglish confirmation: |
|  "Fortune Oil 2 packet aur Tata   |
|   Namak 1kg — Total ₹308."        |
+-----------------------------------+
```

---

## 2. 4-Tier Product Matching Engine

Defined in [app/services/product_matching.py](file:///d:/projectss/Vypaar%20sarthi/app/services/product_matching.py). When a `raw_text` item token is received, four tiers are applied in sequence:

### Tier 1: Exact Barcode / SKU Lookup
Queries `Product.barcode` and `Product.sku` for exact string match. O(1) indexed lookup.

### Tier 2: Product Synonym Table Lookup
Queries `ProductSynonym.term` against the store's synonym index:
```sql
SELECT maps_to_product_id FROM product_synonyms
WHERE store_id = :store_id AND term = :normalized_input
ORDER BY evidence_count DESC;
```
Synonyms are ranked by `evidence_count` — terms confirmed by merchants more times rank higher.

### Tier 3: Phonetic Normalization & Transliteration
The engine normalizes common Hindi/Hinglish lexical variants before matching:

| Spoken Term | Normalized To |
| :--- | :--- |
| `"Tel"`, `"Tael"` | `"oil"` |
| `"Cheeni"`, `"Shakkar"` | `"sugar"` |
| `"Namak"` | `"salt"` |
| `"Atta"`, `"Gehu"` | `"flour"` |
| `"Sabun"` | `"soap"` |
| `"Doodh"` | `"milk"` |

Product names are also run through `Product.normalize_product_name()`:
```python
# normalize_product_name() process:
# 1. unidecode(raw_name)         — converts Unicode to ASCII
# 2. .lower().replace('-', ' ') — lowercases, hyphens → spaces
# 3. re.sub(r'[^\w\s]', '', ...) — strips punctuation
# 4. re.sub(r'\s+', ' ', ...).strip() — collapses whitespace
```

### Tier 4: RapidFuzz Token Similarity Scoring
Compares the normalized input token against all `product.normalized_name` values in the store using RapidFuzz:

| Score Range | Action |
| :--- | :--- |
| **≥ 85%** | **Auto-match** — product added to `matched_items` immediately |
| **60% – 84%** | **Needs clarification** — top candidates returned, merchant asked to choose |
| **< 60%** | **Not found** — error returned; merchant must re-speak or search manually |

---

## 3. Referential Follow-Up Resolution (`MerchantCartSession`)

Merchants frequently say phrases like:
- *"Aur do"* (add 2 more of the same)
- *"2 more"*
- *"Add more"*

The system detects these via `item.get('is_reference')` or by matching a fixed phrase list, then resolves to the **last matched product** stored in the session:
```python
last_item_ref = MerchantCartSession.resolve_reference(current_user.store_id, "item")
if last_item_ref:
    raw_text = last_item_ref.get('raw_text') or last_item_ref.get('name')
```

---

## 4. Merchant Feedback Learning Loop

When a product was ambiguous and the merchant picks the correct one:

1. `POST /api/v1/voice/feedback` is called with `spoken_text` + `chosen_product_id`.
2. `ProductMatchingEngine.record_merchant_correction()` upserts a `ProductSynonym`:
   - If the term already exists for this product: increments `evidence_count` and updates `last_confirmed_at`.
   - If new: creates a new `ProductSynonym` with `is_auto_learned=True`.
3. On the next use of that term, Tier 2 finds it with higher `evidence_count` → auto-matched directly.

This creates a **self-improving feedback loop** where the system becomes more accurate over time per store.

---

## 5. Intent Classification Reference

| Intent | Example Phrase | System Action |
| :--- | :--- | :--- |
| `create_bill` / `add_item` | *"Do packet Maggi aur ek tel"* | Match products → create/update DraftBill |
| `remove_item` | *"Maggi hatao"* | Remove line item from active draft |
| `check_stock` | *"Kitna Fortune Oil bacha hai?"* | Routes to `query_router` — returns stock level |
| `business_query` | *"Aaj sabse zyada kya bika?"* | Routes to Cloud LLM with DB context injection |

---

## 6. Query Router — Local vs Cloud LLM (`QueryRouter`)

The `QueryRouter` classifies whether a user prompt can be answered deterministically:

```
[User Prompt]
     |
     +-- Structured POS intent (create_bill, check_stock)?
     |       → Execute via SQLAlchemy query locally (0 API cost, < 20ms)
     |
     +-- Open-ended analytics / language-heavy query?
             → Inject store context (top products, daily sales etc.)
             → Route to Cloud LLM (Groq / Gemini / Anthropic)
             → Return synthesized natural language answer
```
