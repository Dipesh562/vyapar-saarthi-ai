from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, Product, Inventory, KhataEntry, Customer
from app.services.khata_engine import KhataEngine

class BusinessAssistantQueryRouter:
    @staticmethod
    def answer_query(store_id: int, question: str) -> dict:
        """
        Routes business assistant questions to deterministic SQL templates (AI_SPEC.md §5).
        LLM phrasing guardrail: Numerical values are computed ONLY by SQL, never halluncinated.
        """
        q = question.lower()
        now = datetime.utcnow()

        # Query 1: Today's Total Sales
        if any(term in q for term in ["aaj ka sale", "today sales", "total sale", "today revenue", "aaj ki kamai"]):
            start_today = datetime(now.year, now.month, now.day, 0, 0, 0)
            end_today = datetime(now.year, now.month, now.day, 23, 59, 59)

            res = db.session.query(
                func.coalesce(func.sum(Transaction.total), 0),
                func.count(Transaction.txn_id)
            ).filter(
                Transaction.store_id == store_id,
                Transaction.voided_at.is_(None),
                Transaction.created_at >= start_today,
                Transaction.created_at <= end_today
            ).first()

            total = float(res[0] or 0)
            count = res[1] or 0
            answer = f"Aaj aapke store par total ₹{total:.2f} ki sale hui hai ({count} transactions)."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "sales_today",
                    "result": {"total_revenue": total, "txn_count": count}
                }
            }

        # Query 2: Low Stock Check
        elif any(term in q for term in ["low stock", "kam stock", "kya khatam", "reorder"]):
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
                answer = f"Aapke paas ye items low stock par hain: {', '.join(item_strs)}."
            else:
                answer = "Aapka sabhi stock sufficient hai. Koi item low stock nahi hai."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "low_stock_alert",
                    "result": {"low_stock_items": low_stock_items}
                }
            }

        # Query 3: Customer Udhaar Query (e.g., "Rahul ka udhaar")
        elif "udhaar" in q or "khata" in q or "balance" in q:
            customers = Customer.query.filter_by(store_id=store_id).all()
            customer_balances = []
            for c in customers:
                bal = float(KhataEngine.get_customer_balance(c.customer_id))
                if bal > 0:
                    customer_balances.append({"name": c.name, "balance": bal})

            if customer_balances:
                cust_strs = [f"{cb['name']}: ₹{cb['balance']:.2f}" for cb in customer_balances]
                answer = f"Store ka kul outstanding Udhaar balance: {', '.join(cust_strs)}."
            else:
                answer = "Aapka koi outstanding Udhaar balance baaki nahi hai."

            return {
                "answer_text": answer,
                "data_used": {
                    "query_type": "udhaar_summary",
                    "result": {"customer_balances": customer_balances}
                }
            }

        # General Fallback Answer
        return {
            "answer_text": f"Aapke sawal '{question}' ke liye filhaal automatic SQL template report available hai. Store sales aur stock check kar sakte hain.",
            "data_used": {
                "query_type": "general_query",
                "result": {}
            }
        }
