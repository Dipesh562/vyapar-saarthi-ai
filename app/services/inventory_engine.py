from decimal import Decimal
from app.extensions import db
from app.models import Product, Inventory, InventoryAdjustment, InventoryMovement

class InventoryEngine:
    @staticmethod
    def adjust_stock(store_id: int, product_id: int, user_id: int, quantity_delta: float, reason: str) -> Inventory:
        """
        Adjust stock for a product in a store.
        Creates an InventoryAdjustment audit row (PRD §13 - never a silent overwrite).
        """
        product = Product.query.filter_by(product_id=product_id, store_id=store_id, is_active=True).first()
        if not product:
            raise ValueError("PRODUCT_NOT_FOUND")

        inventory = Inventory.query.filter_by(product_id=product_id).first()
        if not inventory:
            inventory = Inventory(product_id=product_id, quantity_on_hand=0, low_stock_threshold=0)
            db.session.add(inventory)

        delta_dec = Decimal(str(quantity_delta))
        previous_stock = Decimal(str(inventory.quantity_on_hand))
        inventory.quantity_on_hand = previous_stock + delta_dec

        # Log adjustment row
        adjustment = InventoryAdjustment(
            product_id=product_id,
            store_id=store_id,
            quantity_delta=delta_dec,
            reason=reason,
            adjusted_by_user_id=user_id
        )
        db.session.add(adjustment)

        # Log movement row
        movement = InventoryMovement(
            store_id=store_id,
            product_id=product_id,
            movement_type='ADJUSTMENT',
            quantity=delta_dec,
            previous_stock=previous_stock,
            new_stock=inventory.quantity_on_hand,
            reason=reason
        )
        db.session.add(movement)
        db.session.commit()

        return inventory
