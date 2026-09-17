from decimal import Decimal

class VoiceFeedbackService:
    @staticmethod
    def build_stt_failed_message() -> str:
        return "I couldn't understand that. Please say the name again"

    @staticmethod
    def build_clarification_speech_text(question: str, candidates: list) -> str:
        if not candidates:
            return question or "No matching products found. Please search manually."
        
        base_q = question or "Which product did you mean?"
        parts = [base_q]
        for idx, candidate in enumerate(candidates, start=1):
            name = candidate.get('name', 'Unknown product')
            price = candidate.get('price')
            price_str = f" for {price} rupees" if price is not None else ""
            parts.append(f"Option {idx}: {name}{price_str}.")
        
        return " ".join(parts)

    @staticmethod
    def build_readback_text(draft_bill: dict) -> str:
        if not draft_bill or not draft_bill.get('line_items'):
            return "Your bill is empty."

        line_items = draft_bill.get('line_items', [])
        total = draft_bill.get('total')
        if total is None:
            total = draft_bill.get('total_amount', 0)

        item_parts = []
        for item in line_items:
            name = item.get('name', 'Item')
            qty = item.get('quantity', 1)
            unit = item.get('unit', 'unit')
            
            # Format integer quantity cleanly (e.g. 2 instead of 2.0)
            if isinstance(qty, (int, float)) and float(qty).is_integer():
                qty_str = f"{int(qty)}"
            else:
                qty_str = f"{qty}"
            
            line_total = item.get('line_total')
            if line_total is not None:
                lt_val = Decimal(str(line_total))
                item_parts.append(f"{qty_str} {unit} of {name} for {lt_val:.2f} rupees")
            else:
                item_parts.append(f"{qty_str} {unit} of {name}")

        total_dec = Decimal(str(total))
        items_str = ", ".join(item_parts)
        return f"Bill read-back: {items_str}. Total amount is {total_dec:.2f} rupees. Please confirm to complete sale."
