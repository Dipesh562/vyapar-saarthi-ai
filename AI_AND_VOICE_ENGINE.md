# AI_AND_VOICE_ENGINE.md — AI, NLP & Voice Processing Pipeline

> **Ground-truth documentation** — every item here maps directly to running code in the repository.

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
|  - Validates audio bytes (>10B)   |
|  - Passes MIME type + language    |
|    hint (hi-IN / mr-IN / en-IN)   |
|  - Calls Gemini Multimodal API    |
|  - Returns: transcript, confidence|
|  - If GEMINI_API_KEY missing:     |
|    returns STT_UNAVAILABLE error  |
+-----------------------------------+
               |
    confidence < 0.60 → reject (LOW_CONFIDENCE_TRANSCRIPTION)
               |
               v
+-----------------------------------+
|  AI Intent & Entity Extraction    |
|(app/services/ai_orchestration.py) |
|                                   |
|  Priority chain:                  |
|   1. Google Gemini API (primary)  |
|   2. Anthropic Claude (fallback)  |
|   3. Regex parser (local fallback)|
|                                   |
|  Classifies intent (create_bill,  |
|  check_stock, business_query)     |
|  Extracts: items[], customer_name,|
|  payment_status, confidence       |
+-----------------------------------+
               |
     +---------+---------+
     |                   |
     v                   v
[Bill Intents]     [Query Intents]
(create_bill)      (check_stock,
     |              business_query)
     |                   |
     v                   v
+---------------+  +------------------+
| Product       |  | Business Asst.   |
| Matching      |  | Query Router     |
| Engine        |  | (local SQL only) |
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

## 2. Speech-to-Text (STT) — `STTClient`

**File**: [app/services/stt_client.py](file:///d:/projectss/Vypaar%20sarthi/app/services/stt_client.py)

**Provider**: Google Gemini Multimodal Audio API (`google-genai` SDK).  
**Models tried in order**: `gemini-2.0-flash` → `gemini-1.5-flash`.

**What it does**:
- Accepts raw audio bytes (WAV, WebM, MP3, OGG, M4A) and a language hint.
- Sends the audio as a `types.Part` directly to Gemini's multimodal endpoint.
- Returns a structured JSON transcript, confidence score, and detected language.

**Graceful Degradation**:
- If `GEMINI_API_KEY` is not set (or starts with `'mock'`), returns `{"error": "STT_UNAVAILABLE"}`.
- Development and testing bypass STT entirely via the `transcript_text` form field on `/api/v1/voice/transcribe`.

**Confidence threshold**: Transcripts with `confidence < 0.60` are rejected at the route level and trigger a retry prompt.

**Supported audio MIME types**:
| Extension | MIME Type |
| :--- | :--- |
| `.wav` | `audio/wav` (default) |
| `.webm` | `audio/webm` |
| `.mp3` | `audio/mp3` |
| `.ogg` | `audio/ogg` |
| `.m4a` | `audio/m4a` |

---

## 3. AI Intent & Entity Extraction — `AIOrchestrationService`

**File**: [app/services/ai_orchestration.py](file:///d:/projectss/Vypaar%20sarthi/app/services/ai_orchestration.py)

The service converts a free-form spoken transcript into structured JSON using a **three-tier fallback chain**:

### Tier 1: Google Gemini (Primary)
Tries multiple Gemini models in order:
```python
['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-flash-latest']
```
Skipped if `GEMINI_API_KEY` is missing or starts with `'mock'`.

> [!NOTE]
> **Zero API Keys Mode**: If `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are omitted from `.env` (your current setup), the system automatically skips Tiers 1 & 2 and operates **100% on Tier 3 (Local Kirana Regex Fallback)** with zero errors. Cloud LLMs are optional architectural upgrades.

### Tier 2: Anthropic Claude (Fallback)
Model: `claude-3-5-sonnet-20241022`.  
Only called if Gemini fails or is unavailable.  
Skipped if `ANTHROPIC_API_KEY` is missing or starts with `'mock'`.

### Tier 3: Regex Fallback Parser (Always Available)
A deterministic, zero-cost local parser. Handles the most common kirana order patterns using:
- Hinglish number normalization (`"do"` → `2`, `"aadha"` → `0.5`)
- Item chunk splitting on `","`, `"aur"`, `"and"`
- `quantity + unit + product_name` regex pattern matching

### Pipeline Modes
Controlled by `VOICE_PIPELINE_MODE` environment variable (default: `ai_first`):

| Mode | Order |
| :--- | :--- |
| `ai_first` (default) | Preprocess → Gemini → Claude → Regex fallback |
| `legacy` | Regex first → if empty, Gemini → Claude → Regex fallback |

### JSON Output Schema
```json
{
  "intent": "create_bill",
  "items": [
    { "raw_text": "Fortune Oil", "quantity": 2, "unit": "packet", "is_reference": false }
  ],
  "customer_name": "Ramesh",
  "payment_status": "udhaar",
  "confidence": 0.97,
  "needs_clarification": false
}
```

---

## 4. 4-Tier Product Matching Engine

**File**: [app/services/product_matching.py](file:///d:/projectss/Vypaar%20sarthi/app/services/product_matching.py)

When a `raw_text` item token is received, four tiers are applied in sequence:

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

Product names are run through `Product.normalize_product_name()`:
```python
# normalize_product_name() process:
# 1. unidecode(raw_name)           — converts Unicode to ASCII
# 2. .lower().replace('-', ' ')   — lowercases, hyphens → spaces
# 3. re.sub(r'[^\w\s]', '', ...)  — strips punctuation
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

## 5. Referential Follow-Up Resolution (`MerchantCartSession`)

**File**: [app/services/cart_session.py](file:///d:/projectss/Vypaar%20sarthi/app/services/cart_session.py)

Merchants frequently say phrases like:
- *"Aur do"* (add 2 more of the same)
- *"2 more"*
- *"Add more"*

The system detects these via `item.get('is_reference')` or by matching a fixed phrase list, then resolves to the **last matched product** stored in the in-memory session:
```python
last_item_ref = MerchantCartSession.resolve_reference(current_user.store_id, "item")
if last_item_ref:
    raw_text = last_item_ref.get('raw_text') or last_item_ref.get('name')
```

**Session structure** (per store_id):
- `cart` — list of current matched items
- `last_referenced_item` — last product spoken (for *"aur do"* resolution)
- `last_referenced_customer` — last customer spoken (for udhaar context)
- `last_active` — UTC timestamp for 15-minute inactivity timeout

---

## 6. Merchant Feedback Learning Loop

When a product was ambiguous and the merchant picks the correct one:

1. `POST /api/v1/voice/feedback` is called with `spoken_text` + `chosen_product_id`.
2. `ProductMatchingEngine.record_merchant_correction()` upserts a `ProductSynonym`:
   - If the term already exists for this product: increments `evidence_count` and updates `last_confirmed_at`.
   - If new: creates a new `ProductSynonym` with `is_auto_learned=True`.
3. On the next use of that term, Tier 2 finds it with higher `evidence_count` → auto-matched directly.

This creates a **self-improving feedback loop** where the system becomes more accurate over time per store.

---

## 7. Intent Classification Reference

| Intent | Example Phrase | System Action |
| :--- | :--- | :--- |
| `create_bill` | *"Do packet Maggi aur ek tel"* | Match products → create/update DraftBill |
| `check_stock` | *"Kitna Fortune Oil bacha hai?"* | Routes to `BusinessAssistantQueryRouter` → local SQL stock query |
| `business_query` | *"Aaj ka total sale?"* | Routes to `BusinessAssistantQueryRouter` → local SQL summary |

> **Note**: The `remove_item` intent may be extracted by the AI, but the current `/api/v1/voice/process_bill` handler only acts on `create_bill` intents. `check_stock` and `business_query` return a redirect message to the Assistant tab.

---

## 8. Business Assistant Query Router — `BusinessAssistantQueryRouter`

**File**: [app/services/query_router.py](file:///d:/projectss/Vypaar%20sarthi/app/services/query_router.py)

The `BusinessAssistantQueryRouter` answers business questions entirely via **local SQLAlchemy queries** — no external API calls are made. There are three hardcoded SQL templates:

| Query Keyword Match | SQL Operation | Example Response |
| :--- | :--- | :--- |
| `"aaj ka sale"`, `"today sales"`, etc. | `SUM(Transaction.total)` filtered to today | *"Aaj aapke store par total ₹1,240 ki sale hui hai (8 transactions)."* |
| `"low stock"`, `"kam stock"`, etc. | Filter products where `is_low_stock = True` | *"Aapke paas ye items low stock par hain: Green Chilli..."* |
| `"udhaar"`, `"khata"`, `"balance"` | Sum all `KhataEntry` records per customer | *"Store ka kul outstanding Udhaar balance: Ramesh: ₹340."* |

For any query that doesn't match these templates, a generic text fallback is returned explaining which query types are supported. **No cloud LLM is called** from the Query Router.
