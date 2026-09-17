import json
from decimal import Decimal
import uuid
from datetime import datetime
from app.extensions import db
from app.models import Product, Inventory, Transaction, TransactionItem, KhataEntry, InventoryMovement, DraftBill, BillingIdempotency
from app.services.khata_engine import KhataEngine

class BillingEngine:
    @staticmethod
    def create_draft_bill(store_id: int, items: list, customer_id: int = None) -> dict:
        """
        Create a draft bill from validated items.
        Items input format: [{'product_id': 1, 'quantity': 2.0}]
        Returns draft_bill_id, line_items, subtotal, total, and warnings if stock is insufficient.
        """
        if not items or len(items) == 0:
            raise ValueError("EMPTY_ITEM_LIST")

        draft_bill_id = str(uuid.uuid4())
        line_items = []
        warnings = []
        subtotal = Decimal('0.00')

        for item in items:
            product_id = item.get('product_id')
            requested_qty = Decimal(str(item.get('quantity', 1)))

            product = Product.query.filter_by(product_id=product_id, store_id=store_id, is_active=True).first()
            if not product:
                raise ValueError(f"PRODUCT_NOT_FOUND:{product_id}")

            available_stock = Decimal(str(product.inventory.quantity_on_hand)) if product.inventory else Decimal('0')
            if available_stock < requested_qty:
                warnings.append({
                    "code": "INSUFFICIENT_STOCK",
                    "product_id": product_id,
                    "product_name": product.name,
                    "requested": float(requested_qty),
                    "available": float(available_stock)
                })

            unit_price = Decimal(str(product.price))
            line_total = requested_qty * unit_price
            subtotal += line_total

            line_items.append({
                "product_id": product_id,
                "name": product.name,
                "unit": product.unit,
                "quantity": float(requested_qty),
                "unit_price": float(unit_price),
                "line_total": float(line_total)
            })

        draft_obj = DraftBill(
            draft_bill_id=draft_bill_id,
            store_id=store_id,
            customer_id=customer_id,
            line_items_json=json.dumps(line_items),
            subtotal=subtotal,
            total=subtotal,
            warnings_json=json.dumps(warnings),
            created_at=datetime.utcnow()
        )
        db.session.add(draft_obj)
        db.session.commit()

        return draft_obj.to_dict()

    @staticmethod
    def get_draft_bill(draft_bill_id: str, store_id: int) -> dict:
        draft_obj = DraftBill.query.filter_by(draft_bill_id=draft_bill_id, store_id=store_id).first()
        if not draft_obj:
            return None
        return draft_obj.to_dict()

    @staticmethod
    def void_draft_bill(draft_bill_id: str, store_id: int) -> bool:
        draft_obj = DraftBill.query.filter_by(draft_bill_id=draft_bill_id, store_id=store_id).first()
        if draft_obj:
            db.session.delete(draft_obj)
            db.session.commit()
            return True
        return False

    @staticmethod
    def confirm_bill(store_id: int, user_id: int, draft_bill_id: str, payment_status: str, customer_id: int = None, idempotency_key: str = None) -> dict:
        """
        Finalise a bill as a single atomic DB transaction.
        Deducts stock, creates transaction & item rows, and creates Khata entry if on Udhaar.
        Supports idempotency key (API_SPEC.md §5).
        """
        if not idempotency_key:
            raise ValueError("IDEMPOTENCY_KEY_REQUIRED")

        cache_key = f"{store_id}:{idempotency_key}"
        existing_idempotency = BillingIdempotency.query.filter_by(cache_key=cache_key).first()
        if existing_idempotency:
            return json.loads(existing_idempotency.response_json)

        draft_obj = DraftBill.query.filter_by(draft_bill_id=draft_bill_id, store_id=store_id).first()
        if not draft_obj:
            raise ValueError("DRAFT_BILL_NOT_FOUND")

        draft = draft_obj.to_dict()
        effective_customer_id = customer_id or draft.get('customer_id')
        if payment_status == 'udhaar' and not effective_customer_id:
            raise ValueError("CUSTOMER_REQUIRED_FOR_UDHAAR")

        line_items = draft['line_items']
        total_amount = Decimal(str(draft['total']))

        try:
            # Step 1: Re-validate stock for all items
            for item in line_items:
                product_id = item['product_id']
                requested_qty = Decimal(str(item['quantity']))
                inv = Inventory.query.filter_by(product_id=product_id).with_for_update().first()
                if not inv or Decimal(str(inv.quantity_on_hand)) < requested_qty:
                    available = float(inv.quantity_on_hand) if inv else 0.0
                    raise ValueError(f"INSUFFICIENT_STOCK:{product_id}:{item['name']}:{item['quantity']}:{available}")

            # Step 2: Generate daily invoice number (counting only today's invoices for this store)
            now = datetime.utcnow()
            start_of_today = datetime(now.year, now.month, now.day, 0, 0, 0)
            today_str = now.strftime('%Y%m%d')
            count_today = Transaction.query.filter(
                Transaction.store_id == store_id,
                Transaction.created_at >= start_of_today
            ).count() + 1
            invoice_number = f"INV-{today_str}-{count_today:04d}"

            # Step 3: Create Transaction row
            txn = Transaction(
                store_id=store_id,
                customer_id=effective_customer_id,
                total=total_amount,
                payment_status=payment_status,
                invoice_number=invoice_number,
                created_by_user_id=user_id
            )
            db.session.add(txn)
            db.session.flush()

            # Step 4: Create TransactionItem rows & deduct stock
            for item in line_items:
                product_id = item['product_id']
                qty = Decimal(str(item['quantity']))
                u_price = Decimal(str(item['unit_price']))
                l_total = Decimal(str(item['line_total']))

                ti = TransactionItem(
                    txn_id=txn.txn_id,
                    product_id=product_id,
                    quantity=qty,
                    unit_price=u_price,
                    line_total=l_total
                )
                db.session.add(ti)

                inv = Inventory.query.filter_by(product_id=product_id).first()
                previous_stock = Decimal(str(inv.quantity_on_hand))
                inv.quantity_on_hand = previous_stock - qty

                # Log inventory movement
                movement = InventoryMovement(
                    store_id=store_id,
                    product_id=product_id,
                    movement_type='SALE',
                    quantity=qty,
                    previous_stock=previous_stock,
                    new_stock=inv.quantity_on_hand,
                    reason=f"Sale Invoice {invoice_number}"
                )
                db.session.add(movement)

            # Step 5: If Udhaar, add Khata credit entry
            new_khata_balance = None
            if payment_status == 'udhaar':
                KhataEngine.add_credit_entry(
                    customer_id=effective_customer_id,
                    store_id=store_id,
                    user_id=user_id,
                    amount=total_amount,
                    txn_id=txn.txn_id
                )
                db.session.flush()
                new_khata_balance = float(KhataEngine.get_customer_balance(effective_customer_id))

            # Remove draft bill from DB
            db.session.delete(draft_obj)

            response_payload = {
                "message": "Bill confirmed successfully.",
                "txn_id": txn.txn_id,
                "invoice_number": invoice_number,
                "total": float(total_amount),
                "payment_status": payment_status,
                "customer_id": effective_customer_id,
                "new_khata_balance": new_khata_balance
            }

            # Cache idempotency result in DB
            idempotency_obj = BillingIdempotency(
                cache_key=cache_key,
                response_json=json.dumps(response_payload),
                created_at=datetime.utcnow()
            )
            db.session.add(idempotency_obj)
            db.session.commit()

            return response_payload

        except Exception as e:
            db.session.rollback()
            raise e
