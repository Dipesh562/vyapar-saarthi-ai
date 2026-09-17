import re
import unicodedata
from datetime import datetime
from typing import List, Dict, Any
from rapidfuzz import fuzz
from app.models import Product, ProductSynonym

# ─────────────────────────────────────────────────────────────────────────────
# Hindi / Marathi / Devanagari → English mapping for kirana store words.
# Covers: brand names, product types, units, and Marathi/Hindi spoken numbers.
# ─────────────────────────────────────────────────────────────────────────────
DEVANAGARI_KIRANA_MAP = {
    # Generic product types
    'तेल': 'oil', 'ऑयल': 'oil', 'आयल': 'oil', 'आइल': 'oil', 'तैल': 'oil',
    'नमक': 'salt', 'मीठ': 'salt',
    'आटा': 'atta', 'अटा': 'atta', 'आटे': 'atta',
    'दूध': 'milk', 'दुध': 'milk',
    'मक्खन': 'butter', 'लोणी': 'butter',
    'चाय': 'tea', 'चाई': 'tea', 'चहा': 'tea',
    'कॉफी': 'coffee', 'कोफी': 'coffee', 'काफी': 'coffee',
    'चीनी': 'sugar', 'शक्कर': 'sugar', 'साखर': 'sugar',
    'दाल': 'dal',
    'चावल': 'rice', 'तांदूळ': 'rice',
    'बिस्कुट': 'biscuit', 'बिस्किट': 'biscuit',
    'साबुन': 'soap', 'साबू': 'soap',
    'डिटर्जेंट': 'detergent',
    'शैम्पू': 'shampoo',
    'क्रीम': 'cream',
    'टूथपेस्ट': 'toothpaste',
    'मैदा': 'maida',
    'सूजी': 'suji', 'रवा': 'rava',
    'हल्दी': 'haldi turmeric', 'हळद': 'turmeric haldi',
    'मिर्च': 'mirchi chilli', 'मिरची': 'mirchi chilli',
    'धनिया': 'coriander dhania', 'धणे': 'coriander dhania',
    'जीरा': 'jeera cumin', 'जिरे': 'jeera cumin',

    # Common brand names in Devanagari (Hindi & Marathi spellings)
    'फॉर्चून': 'fortune', 'फोर्चून': 'fortune', 'फार्चून': 'fortune', 'फॉर्चन': 'fortune', 'फॉर्च्युन': 'fortune', 'फॉर्च्यून': 'fortune',
    'अमूल': 'amul',
    'आशीर्वाद': 'ashirvaad', 'अशिर्वाद': 'ashirvaad', 'आशिरवाद': 'ashirvaad',
    'टाटा': 'tata',
    'नेस्काफे': 'nescafe', 'नेस्कफे': 'nescafe',
    'रेड': 'red',
    'लेबल': 'label',
    'ब्रूकबॉन्ड': 'brooke bond',
    'सर्फ': 'surf', 'सरफ': 'surf',
    'एक्सेल': 'excel', 'एक्सेल': 'excel',
    'सफोला': 'saffola', 'सेफोला': 'saffola',
    'पतंजलि': 'patanjali', 'पतंजली': 'patanjali',
    'लक्स': 'lux',
    'लाइफबॉय': 'lifebuoy',
    'डेटॉल': 'dettol',
    'कोलगेट': 'colgate',
    'पेप्सोडेंट': 'pepsodent',
    'हेड': 'head', 'शोल्डर': 'shoulder',
    'पार्ले': 'parle', 'पारले': 'parle', 'पारलेजी': 'parle-g',
    'ब्रिटानिया': 'britannia',
    'डाबर': 'dabur',

    # Units
    'पैकेट': 'packet', 'पाकेट': 'packet', 'पैक': 'packet', 'पॅकेट': 'packet', 'पुडा': 'packet', 'पुडे': 'packet',
    'किलो': 'kg', 'किलोग्राम': 'kg', 'किग्रा': 'kg',
    'लीटर': 'litre', 'लिटर': 'litre', 'ली': 'litre',
    'ग्राम': 'gram', 'ग्रा': 'gram', 'ग्': 'gram',
    'मिली': 'ml', 'मिलीलीटर': 'ml',
    'डजन': 'dozen', 'दर्जन': 'dozen',
    'बॉक्स': 'box',

    # Devanagari Digits & Spoken Hindi/Marathi Numbers
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
    'एक': '1', 'वन': '1',
    'दो': '2', 'टू': '2', 'दोन': '2', 'दोनही': '2',
    'तीन': '3', 'थ्री': '3',
    'चार': '4',
    'पांच': '5', 'पाँच': '5', 'पाच': '5',
    'छह': '6', 'छः': '6', 'सहा': '6',
    'सात': '7',
    'आठ': '8',
    'नौ': '9', 'नऊ': '9',
    'दस': '10', 'दहा': '10',
    'आधा': '0.5', 'आधे': '0.5', 'अर्धा': '0.5', 'अर्धी': '0.5', 'अर्धे': '0.5',
    'पाऊण': '0.75', 'डेढ': '1.5', 'डेढ़': '1.5', 'दीड': '1.5', 'अडीच': '2.5',
}

# Normalize map keys to NFC
DEVANAGARI_KIRANA_MAP = {unicodedata.normalize('NFC', k): v for k, v in DEVANAGARI_KIRANA_MAP.items()}

ROMANIZED_NUMBER_MAP = {
    'ek': '1', 'do': '2', 'don': '2', 'teen': '3', 'char': '4', 'chaar': '4',
    'paanch': '5', 'panch': '5', 'paach': '5', 'chhah': '6', 'chhe': '6', 'saha': '6',
    'saat': '7', 'aath': '8', 'nau': '9', 'nauu': '9', 'das': '10', 'daha': '10',
    'aadha': '0.5', 'aadhe': '0.5', 'ardha': '0.5', 'dedh': '1.5', 'deed': '1.5', 'dhai': '2.5', 'adeech': '2.5',
}


def _normalize_multilingual(text: str) -> str:
    """
    Normalize a product query that may contain Devanagari (Hindi/Marathi), Hinglish, or English.
    """
    if not text:
        return ""

    text = unicodedata.normalize('NFC', text)
    words = text.strip().split()
    result_words = []

    for w in words:
        clean = re.sub(r'^[।,!?.\-\s]+|[।,!?.\-\s]+$', '', w)
        clean = unicodedata.normalize('NFC', clean)
        if not clean:
            continue

        if clean in DEVANAGARI_KIRANA_MAP:
            result_words.append(DEVANAGARI_KIRANA_MAP[clean])
        else:
            try:
                from unidecode import unidecode
                trans = unidecode(clean).lower()
                trans = re.sub(r'[^a-z0-9]', '', trans)
                if trans:
                    result_words.append(trans)
                else:
                    result_words.append(clean.lower())
            except ImportError:
                result_words.append(clean.lower())

    joined = ' '.join(result_words)
    final_words = []
    for w in joined.split():
        final_words.append(ROMANIZED_NUMBER_MAP.get(w.lower(), w))
    joined = ' '.join(final_words)
    joined = re.sub(r'[^\w\s]', '', joined)
    return re.sub(r'\s+', ' ', joined).strip()


class ProductMatchingEngine:
    @staticmethod
    def _get_product_sale_counts(store_id: int) -> Dict[int, float]:
        """
        Retrieves total quantity sold for each product in the store from TransactionItem.
        """
        try:
            from app.models import Transaction, TransactionItem
            from app.extensions import db
            from sqlalchemy import func

            results = db.session.query(
                TransactionItem.product_id,
                func.sum(TransactionItem.quantity)
            ).join(
                Transaction, Transaction.txn_id == TransactionItem.txn_id
            ).filter(
                Transaction.store_id == store_id
            ).group_by(
                TransactionItem.product_id
            ).all()

            return {r[0]: float(r[1] or 0.0) for r in results}
        except Exception as e:
            print(f"[ProductMatchingEngine] Sale count query notice: {e}")
            return {}

    @staticmethod
    def record_merchant_correction(store_id: int, spoken_text: str, product_id: int) -> ProductSynonym:
        """
        Learns a merchant synonym mapping from user feedback (Component 5).
        Increments evidence_count if mapping already exists, or creates a new auto-learned synonym.
        """
        from app.extensions import db

        term = _normalize_multilingual(spoken_text) if spoken_text else ""
        if not term:
            term = (spoken_text or "").strip().lower()

        if not term:
            return None

        synonym = ProductSynonym.query.filter_by(
            store_id=store_id,
            term=term,
            maps_to_product_id=product_id
        ).first()

        if synonym:
            synonym.evidence_count = (synonym.evidence_count or 1) + 1
            synonym.last_confirmed_at = datetime.utcnow()
        else:
            synonym = ProductSynonym(
                store_id=store_id,
                term=term,
                maps_to_product_id=product_id,
                evidence_count=1,
                last_confirmed_at=datetime.utcnow(),
                is_auto_learned=True
            )
            db.session.add(synonym)

        db.session.commit()
        return synonym

    @staticmethod
    def match_product(store_id: int, raw_text: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Multi-stage product matching pipeline (PRODUCT_MATCHING.md §1-§5).
        Supports Hindi/Devanagari/Hinglish/English queries via multilingual normalization.
        Includes Stage 1 Synonym learning & conflict resolution, plus Stage 3 Popularity weighting.
        """
        if not raw_text:
            return {"matched": False, "needs_clarification": False, "product": None, "candidates": []}

        normalized_query = _normalize_multilingual(raw_text)
        std_normalized = Product.normalize_product_name(raw_text)

        # ── Stage 1: Check Synonyms Table (with conflict resolution) ──
        for q in [normalized_query, std_normalized, raw_text.lower().strip()]:
            if not q:
                continue
            synonyms = ProductSynonym.query.filter(
                (ProductSynonym.store_id == store_id) | (ProductSynonym.store_id.is_(None)),
                ProductSynonym.term.ilike(q)
            ).all()

            if synonyms:
                # Check for conflict: multiple learned synonyms for the same term with evidence_count >= 3
                active_conflicts = [s for s in synonyms if s.maps_to_product_id and (s.evidence_count or 1) >= 3]
                unique_product_ids = {s.maps_to_product_id for s in active_conflicts}

                if len(unique_product_ids) > 1:
                    candidate_products = Product.query.filter(
                        Product.product_id.in_(list(unique_product_ids)),
                        Product.store_id == store_id,
                        Product.is_active == True
                    ).all()
                    if candidate_products:
                        return {
                            "matched": False,
                            "needs_clarification": True,
                            "confidence": 0.6,
                            "product": None,
                            "clarification_question": f"Multiple products learned for term '{raw_text}'. Which one did you mean?",
                            "candidates": [{
                                "product_id": c.product_id,
                                "name": c.name,
                                "unit": c.unit,
                                "price": float(c.price),
                                "brand": c.brand
                            } for c in candidate_products]
                        }

                # Return the highest-evidence matching synonym product
                synonyms_sorted = sorted(synonyms, key=lambda s: (s.evidence_count or 1), reverse=True)
                for s in synonyms_sorted:
                    if s.maps_to_product_id:
                        product = Product.query.filter_by(product_id=s.maps_to_product_id, store_id=store_id, is_active=True).first()
                        if product:
                            return {
                                "matched": True,
                                "needs_clarification": False,
                                "confidence": 1.0,
                                "product": product,
                                "candidates": []
                            }

        # Fetch all active products in store
        products = Product.query.filter_by(store_id=store_id, is_active=True).all()
        if not products:
            return {"matched": False, "needs_clarification": False, "product": None, "candidates": []}

        # Stage 2: Calculate base scores for all products
        raw_scored = []
        for p in products:
            p_norm = p.normalized_name

            # Exact match on normalized name -> immediate 1.0 match
            if p_norm == normalized_query or p_norm == std_normalized:
                return {
                    "matched": True,
                    "needs_clarification": False,
                    "confidence": 1.0,
                    "product": p,
                    "candidates": []
                }

            score = max(
                float(fuzz.WRatio(normalized_query, p_norm)),
                float(fuzz.WRatio(std_normalized, p_norm)),
                float(fuzz.token_set_ratio(normalized_query, p_norm)),
                float(fuzz.token_set_ratio(std_normalized, p_norm)),
            )

            # Brand & Category boosting
            query_words = set(normalized_query.split()) | set(std_normalized.split())
            if p.brand:
                brand_lower = p.brand.lower()
                brand_norm = _normalize_multilingual(p.brand)
                if brand_lower in normalized_query or brand_norm in normalized_query or brand_lower in query_words:
                    score += 20.0
                else:
                    all_brands = {prod.brand.lower() for prod in products if prod.brand}
                    if any(b in query_words for b in all_brands if b != brand_lower):
                        score -= 30.0

            if p.category and p.category.lower() in query_words:
                score += 10.0

            raw_scored.append((score, p))

        raw_scored.sort(key=lambda x: x[0], reverse=True)

        # Stage 3: Popularity tie-breaker ceiling rule
        sale_counts = ProductMatchingEngine._get_product_sale_counts(store_id)
        top_raw_score = raw_scored[0][0]
        second_raw_score = raw_scored[1][0] if len(raw_scored) > 1 else 0.0
        fuzzy_gap = top_raw_score - second_raw_score

        # Popularity bonus (+5 per 10 sales, max +15) ONLY applies if fuzzy gap <= 10.0 points
        apply_popularity = (fuzzy_gap <= 10.0)

        final_scored = []
        for score, p in raw_scored:
            final_score = score
            if apply_popularity:
                sold_qty = sale_counts.get(p.product_id, 0.0)
                pop_bonus = min(15.0, (sold_qty / 10.0) * 5.0)
                final_score += pop_bonus
            final_scored.append((final_score, p))

        final_scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top_product = final_scored[0]

        # High confidence match (score >= 70)
        if top_score >= 70:
            if len(final_scored) > 1 and (top_score - final_scored[1][0]) <= 5:
                candidates = [p for s, p in final_scored[:top_k] if s >= 50]
                return {
                    "matched": False,
                    "needs_clarification": True,
                    "confidence": min(top_score / 100.0, 1.0),
                    "product": None,
                    "clarification_question": f"Multiple items matched '{raw_text}'. Which one do you mean?",
                    "candidates": [{
                        "product_id": c.product_id,
                        "name": c.name,
                        "unit": c.unit,
                        "price": float(c.price),
                        "brand": c.brand
                    } for c in candidates]
                }

            return {
                "matched": True,
                "needs_clarification": False,
                "confidence": min(top_score / 100.0, 1.0),
                "product": top_product,
                "candidates": []
            }

        # Moderate confidence (50-69) -> trigger clarification
        elif top_score >= 50:
            candidates = [p for s, p in final_scored[:top_k] if s >= 40]
            return {
                "matched": False,
                "needs_clarification": True,
                "confidence": min(top_score / 100.0, 1.0),
                "product": None,
                "clarification_question": f"Did you mean one of these for '{raw_text}'?",
                "candidates": [{
                    "product_id": c.product_id,
                    "name": c.name,
                    "unit": c.unit,
                    "price": float(c.price),
                    "brand": c.brand
                } for c in candidates]
            }

        # Low confidence -> not found
        return {
            "matched": False,
            "needs_clarification": False,
            "confidence": min(top_score / 100.0, 1.0),
            "product": None,
            "candidates": []
        }
