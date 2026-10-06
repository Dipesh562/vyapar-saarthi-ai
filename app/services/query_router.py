import re
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, TransactionItem, Product, Inventory, KhataEntry, Customer, Store
from app.services.khata_engine import KhataEngine
from app.services.product_matching import ProductMatchingEngine


class BusinessAssistantQueryRouter:
    @staticmethod
    def _resolve_language(question: str, language: str = None, store_id: int = None) -> str:
        """
        Resolves query language into canonical code ('mr', 'hi', 'en').
        Priority:
        1. Explicitly requested language from UI/client
        2. Strong Marathi/English keyword patterns in the question
        3. Store language preference from DB
        4. Default fallback ('hi')
        """
        if language:
            lang_lower = language.lower()
            if lang_lower.startswith('mr'):
                return 'mr'
            elif lang_lower.startswith('en'):
                return 'en'
            elif lang_lower.startswith('hi'):
                return 'hi'

        q_lower = question.lower()

        # Marathi markers
        marathi_markers = [
            "kiti", "zali", "jhali", "aahe", "vikla", "vikli", "vikle", "konta", "konti",
            "saglyat", "sagleat", "banle", "aajchi", "kalchi", "sarashari", "mahinyat",
            "athavada", "athavdyat", "divas", "sang", "madhe", "madhye", "paise", "ale",
            "sagle", "aajcha", "kalcha", "sarv"
        ]
        if any(re.search(r'\b' + re.escape(marker) + r'\b', q_lower) for marker in marathi_markers):
            return 'mr'

        # English markers
        english_markers = [
            "today", "yesterday", "how much", "how many", "sales", "revenue",
            "sold", "bills", "average", "best selling", "top selling", "what is", "did i sell"
        ]
        has_hindi_markers = any(w in q_lower for w in [
            "aaj", "kal", "kitna", "kitni", "bika", "biki", "bane", "hai",
            "hua", "hui", "ka", "ki", "ke", "ko", "kamai", "udhaar"
        ])
        if any(re.search(r'\b' + re.escape(m) + r'\b', q_lower) for m in english_markers) and not has_hindi_markers:
            return 'en'

        if store_id:
            try:
                store = db.session.get(Store, store_id)
                if store and store.language_pref:
                    pref = store.language_pref.lower()
                    if pref.startswith('mr'):
                        return 'mr'
                    elif pref.startswith('en'):
                        return 'en'
                    elif pref.startswith('hi'):
                        return 'hi'
            except Exception:
                pass

        return 'hi'

    @staticmethod
    def _get_time_window(time_range: str):
        """
        Calculates UTC start and end bounds corresponding to local store time (IST).
        Returns: (start_datetime, end_datetime, label_mr, label_hi, label_en)
        """
        ist = timezone(timedelta(hours=5, minutes=30))
        now_utc = datetime.now(timezone.utc)
        now_ist = datetime.now(ist)

        if time_range == 'yesterday':
            yest_ist = now_ist - timedelta(days=1)
            start_ist = datetime(yest_ist.year, yest_ist.month, yest_ist.day, 0, 0, 0, tzinfo=ist)
            end_ist = datetime(yest_ist.year, yest_ist.month, yest_ist.day, 23, 59, 59, 999999, tzinfo=ist)
            start = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
            end = end_ist.astimezone(timezone.utc).replace(tzinfo=None)
            return start, end, "काल", "कल", "yesterday"
        elif time_range == 'last_7_days':
            start = (now_utc - timedelta(days=7)).replace(tzinfo=None)
            end = now_utc.replace(tzinfo=None)
            return start, end, "मागील ७ दिवसांत", "पिछले 7 दिनों में", "in the last 7 days"
        elif time_range == 'this_month':
            start_ist = datetime(now_ist.year, now_ist.month, 1, 0, 0, 0, tzinfo=ist)
            start = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
            end = now_utc.replace(tzinfo=None)
            return start, end, "या महिन्यात", "इस महीने", "this month"
        else:  # today
            start_ist = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=ist)
            end_ist = datetime(now_ist.year, now_ist.month, now_ist.day, 23, 59, 59, 999999, tzinfo=ist)
            start_utc_ist = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
            end_utc_ist = end_ist.astimezone(timezone.utc).replace(tzinfo=None)
            # Encompass both IST day and UTC day to handle both UTC and local server environments
            start = min(start_utc_ist, datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0))
            end = max(end_utc_ist, datetime(now_utc.year, now_utc.month, now_utc.day, 23, 59, 59))
            return start, end, "आज", "आज", "today"

    @staticmethod
    def answer_query(store_id: int, question: str, language: str = None) -> dict:
        """
        Routes business assistant questions to deterministic SQL templates.
        Guaranteed: Numerical values are computed ONLY by SQL, never hallucinated by an LLM.
        Responses are generated strictly in the merchant's resolved language ('mr', 'hi', 'en').
        """
        q = question.strip().lower()
        lang = BusinessAssistantQueryRouter._resolve_language(question, language, store_id)

        # ── Detect Time Range ──
        if any(term in q for term in ["kal", "kalchi", "kalcha", "kalche", "yesterday"]):
            time_range = "yesterday"
        elif any(term in q for term in ["week", "hafta", "hafte", "athavada", "athavdyat", "7 days", "sat divas", "pichle 7"]):
            time_range = "last_7_days"
        elif any(term in q for term in ["month", "mahina", "mahine", "mahinyat"]):
            time_range = "this_month"
        else:
            time_range = "today"

        start_time, end_time, label_mr, label_hi, label_en = BusinessAssistantQueryRouter._get_time_window(time_range)

        # ── Query Type 1: Low Stock Check ──
        if any(term in q for term in ["low stock", "kam stock", "kya khatam", "reorder", "stock kami", "stock check"]):
            products = Product.query.filter_by(store_id=store_id, is_active=True).all()
            low_stock_items = []
            for p in products:
                if p.inventory and p.inventory.is_low_stock:
                    low_stock_items.append({
                        "name": p.name,
                        "quantity_on_hand": float(p.inventory.quantity_on_hand),
                        "unit": p.unit
                    })

            if low_stock_items:
                item_strs = [f"{item['name']} ({item['quantity_on_hand']} {item['unit']})" for item in low_stock_items]
                joined = ", ".join(item_strs)
                if lang == 'mr':
                    answer = f"तुमच्याकडे हे प्रॉडक्ट्स कमी स्टॉकमध्ये आहेत: {joined}."
                elif lang == 'en':
                    answer = f"The following items are low in stock: {joined}."
                else:
                    answer = f"आपके पास ये आइटम्स कम स्टॉक पर हैं: {joined}."
            else:
                if lang == 'mr':
                    answer = "सर्व प्रॉडक्ट्सचा स्टॉक पुरेसा आहे. कोणताही आयटम कमी नाही."
                elif lang == 'en':
                    answer = "All stock levels are sufficient. No items are low in stock."
                else:
                    answer = "आपका सभी स्टॉक पर्याप्त है. कोई आइटम कम स्टॉक पर नहीं है."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "low_stock_alert",
                    "result": {"low_stock_items": low_stock_items}
                }
            }

        # ── Query Type 2: Customer Udhaar / Khata Balance ──
        if any(term in q for term in ["udhaar", "khata", "balance", "udhari"]):
            customers = Customer.query.filter_by(store_id=store_id).all()
            customer_balances = []
            for c in customers:
                bal = float(KhataEngine.get_customer_balance(c.customer_id))
                if bal > 0:
                    customer_balances.append({"name": c.name, "balance": bal})

            if customer_balances:
                cust_strs = [f"{cb['name']}: ₹{cb['balance']:.2f}" for cb in customer_balances]
                joined = ", ".join(cust_strs)
                if lang == 'mr':
                    answer = f"दुकानाचे एकूण बाकी उधारी: {joined}."
                elif lang == 'en':
                    answer = f"Total outstanding customer balance: {joined}."
                else:
                    answer = f"दुकान का कुल बकाया उधार: {joined}."
            else:
                if lang == 'mr':
                    answer = "कोणतीही उधारी बाकी नाही."
                elif lang == 'en':
                    answer = "No outstanding customer balance remaining."
                else:
                    answer = "कोई उधार बकाया नहीं है."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "udhaar_summary",
                    "result": {"customer_balances": customer_balances}
                }
            }

        # ── Query Type 3: Number of Bills / Transactions ──
        is_bill_count_query = any(term in q for term in [
            "kiti bill", "kiti bills", "kitne bill", "kitne bills", "how many bill",
            "how many bills", "bill banle", "bills banle", "bill bane", "bills bane",
            "total bill", "total bills", "kitna bill"
        ])
        if is_bill_count_query:
            res = db.session.query(
                func.count(Transaction.txn_id),
                func.coalesce(func.sum(Transaction.total), 0)
            ).filter(
                Transaction.store_id == store_id,
                Transaction.voided_at.is_(None),
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time
            ).first()

            count = res[0] or 0
            total = float(res[1] or 0)

            if lang == 'mr':
                answer = f"{label_mr} तुमच्या दुकानात एकूण {count} बिल्स बनले आहेत (एकूण विक्री ₹{total:.2f})."
            elif lang == 'en':
                answer = f"A total of {count} bills were created {label_en} (total sales ₹{total:.2f})."
            else:
                answer = f"{label_hi} दुकान पर कुल {count} बिल्स बने हैं (कुल बिक्री ₹{total:.2f})."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "bill_count",
                    "result": {"txn_count": count, "total_revenue": total, "time_range": time_range}
                }
            }

        # ── Query Type 4: Average Bill Value ──
        is_avg_bill_query = any(term in q for term in ["average", "avg", "sarashari", "madhya", "ausat"])
        if is_avg_bill_query:
            res = db.session.query(
                func.coalesce(func.sum(Transaction.total), 0),
                func.count(Transaction.txn_id)
            ).filter(
                Transaction.store_id == store_id,
                Transaction.voided_at.is_(None),
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time
            ).first()

            total = float(res[0] or 0)
            count = res[1] or 0
            avg_bill = (total / count) if count > 0 else 0.0

            if count > 0:
                if lang == 'mr':
                    answer = f"{label_mr}चे सरासरी बिल मूल्य (Average Bill) ₹{avg_bill:.2f} आहे (एकूण {count} बिल्स)."
                elif lang == 'en':
                    answer = f"{label_en.capitalize()}'s average bill value is ₹{avg_bill:.2f} across {count} transactions."
                else:
                    answer = f"{label_hi} का औसत बिल (Average Bill) ₹{avg_bill:.2f} है (कुल {count} बिल्स)."
            else:
                if lang == 'mr':
                    answer = f"{label_mr} अद्याप कोणतीही विक्री झालेली नाही, त्यामुळे सरासरी बिल उपलब्ध नाही."
                elif lang == 'en':
                    answer = f"No sales recorded {label_en} yet, so average bill value is not available."
                else:
                    answer = f"{label_hi} अभी तक कोई बिक्री नहीं हुई है, इसलिए औसत बिल उपलब्ध नहीं है."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "average_bill",
                    "result": {"average_bill": avg_bill, "total_revenue": total, "txn_count": count}
                }
            }

        # ── Query Type 5: Best-Selling Product ──
        is_top_product_query = any(term in q for term in [
            "saglyat jast", "sagleat jast", "saglyat jasta", "sabse jyada", "sabse jada",
            "best selling", "top selling", "most sold", "top product"
        ])
        if is_top_product_query:
            top_query = db.session.query(
                TransactionItem.product_id,
                Product.name,
                Product.unit,
                func.coalesce(func.sum(TransactionItem.quantity), 0).label('total_qty'),
                func.coalesce(func.sum(TransactionItem.line_total), 0).label('total_rev')
            ).join(
                Transaction, Transaction.txn_id == TransactionItem.txn_id
            ).join(
                Product, Product.product_id == TransactionItem.product_id
            ).filter(
                Transaction.store_id == store_id,
                Transaction.voided_at.is_(None)
            )

            # Apply time filter if explicitly stated
            has_explicit_time = any(t in q for t in ["aaj", "kal", "today", "yesterday", "week", "hafte", "month", "mahina"])
            if has_explicit_time:
                top_query = top_query.filter(
                    Transaction.created_at >= start_time,
                    Transaction.created_at <= end_time
                )
                time_lbl_mr = label_mr
                time_lbl_hi = label_hi
                time_lbl_en = label_en
            else:
                time_lbl_mr = "एकूण"
                time_lbl_hi = "कुल"
                time_lbl_en = "overall"

            top_item = top_query.group_by(
                TransactionItem.product_id,
                Product.name,
                Product.unit
            ).order_by(
                func.sum(TransactionItem.quantity).desc()
            ).first()

            if top_item:
                prod_name = top_item[1]
                prod_unit = top_item[2] or "unit"
                qty = float(top_item[3] or 0)
                qty_str = f"{int(qty)}" if qty.is_integer() else f"{qty:.2f}"
                rev = float(top_item[4] or 0)

                if lang == 'mr':
                    answer = f"{time_lbl_mr} सर्वात जास्त विकले गेलेले प्रॉडक्ट '{prod_name}' आहे ({qty_str} {prod_unit}, एकूण ₹{rev:.2f})."
                elif lang == 'en':
                    answer = f"The best-selling product {time_lbl_en} is '{prod_name}' ({qty_str} {prod_unit}, total ₹{rev:.2f})."
                else:
                    answer = f"{time_lbl_hi} सबसे ज़्यादा बिकने वाला प्रोडक्ट '{prod_name}' है ({qty_str} {prod_unit}, कुल ₹{rev:.2f})."

                return {
                    "answer_text": answer,
                    "data_used": {
                        "query_type": "top_selling_product",
                        "result": {"product_name": prod_name, "quantity": qty, "unit": prod_unit, "revenue": rev}
                    }
                }
            else:
                if lang == 'mr':
                    answer = f"{time_lbl_mr} कोणतीही विक्री झालेली नाही."
                elif lang == 'en':
                    answer = f"No sales recorded {time_lbl_en}."
                else:
                    answer = f"{time_lbl_hi} कोई बिक्री नहीं हुई है."

                return {
                    "answer_text": answer,
                    "data_used": {
                        "query_type": "top_selling_product",
                        "result": None
                    }
                }

        # ── Query Type 6: Specific Product Sales / Quantity ──
        # Check if query asks for a specific product's sale (e.g. "Maggi kiti vikli?", "Fortune oil kitna bika?")
        # Strip noise words to isolate candidate product name
        candidate = q
        noise_patterns = [
            r'\b(last\s+7\s+days|pichle\s+7\s+din|7\s+days|sat\s+divas|ya\s+week|is\s+hafte|this\s+month|is\s+mahine|ya\s+mahinyat|aajchi|aajcha|kalchi|kalcha|aaj|kal|today|yesterday)\b',
            r'\b(madhe|madhye|mein|me|pe|kiti|kitna|kitni|kitne|vikli|vikla|vikle|bika|biki|bike|biko|sold|sell|sale|sales|total|sang|batao|bata|bol|de|aahe|hai|zali|jhali|hua|hui|banle|bane|ki|ka|ke|ko|par|se|la|che|chi|cha|did|how|much|many|was|i)\b'
        ]
        for pat in noise_patterns:
            candidate = re.sub(pat, ' ', candidate, flags=re.IGNORECASE)
        candidate = re.sub(r'[^\w\s]', ' ', candidate)
        candidate = re.sub(r'\s+', ' ', candidate).strip()

        sales_nouns = {"sale", "sales", "vikri", "kamai", "paise", "dhandha", "revenue", "business", "bill", "bills", ""}
        is_candidate_valid = bool(candidate and len(candidate) >= 2 and candidate.lower() not in sales_nouns)

        if is_candidate_valid:
            match_res = ProductMatchingEngine.match_product(store_id, candidate)
            matched_prod = match_res.get('product')

            if matched_prod:
                has_explicit_time = any(t in q for t in ["aaj", "kal", "today", "yesterday", "week", "hafte", "month", "mahina", "7 days"])
                prod_q = db.session.query(
                    func.coalesce(func.sum(TransactionItem.quantity), 0),
                    func.coalesce(func.sum(TransactionItem.line_total), 0)
                ).join(
                    Transaction, Transaction.txn_id == TransactionItem.txn_id
                ).filter(
                    Transaction.store_id == store_id,
                    Transaction.voided_at.is_(None),
                    TransactionItem.product_id == matched_prod.product_id
                )

                if has_explicit_time:
                    prod_q = prod_q.filter(
                        Transaction.created_at >= start_time,
                        Transaction.created_at <= end_time
                    )
                    time_lbl_mr = label_mr
                    time_lbl_hi = label_hi
                    time_lbl_en = label_en
                else:
                    time_lbl_mr = "एकूण"
                    time_lbl_hi = "कुल"
                    time_lbl_en = "overall"

                res = prod_q.first()
                qty = float(res[0] or 0)
                rev = float(res[1] or 0)
                unit = matched_prod.unit or "unit"
                qty_str = f"{int(qty)}" if qty.is_integer() else f"{qty:.2f}"

                if qty > 0:
                    if lang == 'mr':
                        answer = f"{time_lbl_mr} '{matched_prod.name}' चे एकूण {qty_str} {unit} विकले गेले (एकूण विक्री ₹{rev:.2f})."
                    elif lang == 'en':
                        answer = f"{time_lbl_en.capitalize()}, a total of {qty_str} {unit} of '{matched_prod.name}' was sold (total sales ₹{rev:.2f})."
                    else:
                        answer = f"{time_lbl_hi} '{matched_prod.name}' के कुल {qty_str} {unit} बिके हैं (कुल बिक्री ₹{rev:.2f})."
                else:
                    if lang == 'mr':
                        answer = f"{time_lbl_mr} '{matched_prod.name}' ची कोणतीही विक्री झालेली नाही."
                    elif lang == 'en':
                        answer = f"No sales of '{matched_prod.name}' recorded {time_lbl_en}."
                    else:
                        answer = f"{time_lbl_hi} '{matched_prod.name}' की कोई बिक्री नहीं हुई है."

                return {
                    "answer_text": answer,
                    "data_used": {
                        "query_type": "product_sales",
                        "result": {
                            "product_id": matched_prod.product_id,
                            "product_name": matched_prod.name,
                            "quantity": qty,
                            "unit": unit,
                            "revenue": rev
                        }
                    }
                }
            elif any(verb in q for verb in ["vikli", "vikla", "vikle", "bika", "biki", "bike", "sold"]):
                # Explicit product sale question, but candidate not found in store
                if lang == 'mr':
                    answer = f"तुमच्या दुकानात '{candidate}' हे प्रॉडक्ट सापडले नाही."
                elif lang == 'en':
                    answer = f"Product '{candidate}' was not found in your store inventory."
                else:
                    answer = f"आपकी दुकान में '{candidate}' प्रोडक्ट नहीं मिला."

                return {
                    "answer_text": answer,
                    "data_used": {
                        "query_type": "product_not_found",
                        "result": {"searched_term": candidate}
                    }
                }

        # ── Query Type 7: Total Sales (Today, Yesterday, Last 7 Days, Month) ──
        is_sales_query = any(term in q for term in [
            "sale", "sales", "vikri", "kamai", "paise", "dhandha", "revenue", "sell", "sold", "business",
            "kitna hua", "kiti zali", "kiti jhali", "kitna aaya", "ale", "aale", "how much"
        ]) or time_range in ["yesterday", "last_7_days", "this_month"]


        if is_sales_query:
            res = db.session.query(
                func.coalesce(func.sum(Transaction.total), 0),
                func.count(Transaction.txn_id)
            ).filter(
                Transaction.store_id == store_id,
                Transaction.voided_at.is_(None),
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time
            ).first()

            total = float(res[0] or 0)
            count = res[1] or 0

            if lang == 'mr':
                if time_range == 'yesterday':
                    answer = f"काल तुमच्या दुकानात एकूण ₹{total:.2f} ची विक्री झाली होती ({count} बिल्स)."
                elif time_range == 'last_7_days':
                    answer = f"मागील ७ दिवसांत तुमच्या दुकानात एकूण ₹{total:.2f} ची विक्री झाली आहे ({count} बिल्स)."
                elif time_range == 'this_month':
                    answer = f"या महिन्यात तुमच्या दुकानात एकूण ₹{total:.2f} ची विक्री झाली आहे ({count} बिल्स)."
                else:
                    answer = f"आज तुमच्या दुकानात एकूण ₹{total:.2f} ची विक्री झाली आहे ({count} बिल्स)."
            elif lang == 'en':
                if time_range == 'yesterday':
                    answer = f"Yesterday's total sales were ₹{total:.2f} across {count} transactions."
                elif time_range == 'last_7_days':
                    answer = f"Total sales in the last 7 days are ₹{total:.2f} across {count} transactions."
                elif time_range == 'this_month':
                    answer = f"Total sales this month are ₹{total:.2f} across {count} transactions."
                else:
                    answer = f"Today's total sales are ₹{total:.2f} across {count} transactions."
            else:  # Hindi
                if time_range == 'yesterday':
                    answer = f"कल आपकी दुकान पर कुल ₹{total:.2f} की बिक्री हुई थी ({count} बिल्स)."
                elif time_range == 'last_7_days':
                    answer = f"पिछले 7 दिनों में कुल ₹{total:.2f} की बिक्री हुई है ({count} बिल्स)."
                elif time_range == 'this_month':
                    answer = f"इस महीने में कुल ₹{total:.2f} की बिक्री हुई है ({count} बिल्स)."
                else:
                    answer = f"आज आपकी दुकान पर कुल ₹{total:.2f} की बिक्री हुई है ({count} बिल्स)."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": f"sales_{time_range}",
                    "result": {"total_revenue": total, "txn_count": count, "time_range": time_range}
                }
            }

        # ── General Fallback Answer ──
        if lang == 'mr':
            fallback_text = (
                f"तुमच्या '{question}' या प्रश्नासाठी माहिती उपलब्ध नाही. "
                "तुम्ही विचारू शकता: 'आज किती सेल झाली?', 'काल किती विक्री झाली?', "
                "'आज किती बिल्स बनले?', किंवा 'मॅगी किती विकली?'."
            )
        elif lang == 'en':
            fallback_text = (
                f"I couldn't find an answer for '{question}'. "
                "You can ask: 'Today's sales', 'Yesterday's sales', 'How many bills today?', "
                "or 'How much Maggi was sold?'."
            )
        else:
            fallback_text = (
                f"आपके सवाल '{question}' के लिए जानकारी उपलब्ध नहीं है. "
                "आप पूछ सकते हैं: 'आज कितनी सेल हुई?', 'कल कितनी सेल हुई?', "
                "'आज कितने बिल बने?', या 'मैगी कितनी बिकी?'."
            )

        return {
            "answer_text": fallback_text,
            "data_used": {
                "query_type": "general_query",
                "result": {}
            }
        }

