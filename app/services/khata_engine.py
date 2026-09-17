from decimal import Decimal
from sqlalchemy import func, case
from app.extensions import db
from app.models import KhataEntry, Customer

class KhataEngine:
    @staticmethod
    def get_customer_balance(customer_id: int) -> Decimal:
        """
        Derive customer balance from ledger history (PRD §14, DATABASE_SCHEMA.md §5).
        Balance = SUM(credit) - SUM(payment)
        Never read from a stored column!
        """
        result = db.session.query(
            func.coalesce(func.sum(case((KhataEntry.type == 'credit', KhataEntry.amount), else_=0)), 0) -
            func.coalesce(func.sum(case((KhataEntry.type == 'payment', KhataEntry.amount), else_=0)), 0)
        ).filter(KhataEntry.customer_id == customer_id).scalar()
        
        return Decimal(str(result or 0))

    @staticmethod
    def add_credit_entry(customer_id: int, store_id: int, user_id: int, amount: Decimal, txn_id: int = None) -> KhataEntry:
        entry = KhataEntry(
            customer_id=customer_id,
            store_id=store_id,
            txn_id=txn_id,
            amount=amount,
            type='credit',
            recorded_by_user_id=user_id
        )
        db.session.add(entry)
        return entry

    @staticmethod
    def add_payment_entry(customer_id: int, store_id: int, user_id: int, amount: Decimal) -> KhataEntry:
        entry = KhataEntry(
            customer_id=customer_id,
            store_id=store_id,
            amount=amount,
            type='payment',
            recorded_by_user_id=user_id
        )
        db.session.add(entry)
        return entry
