import time
import uuid
from typing import Dict, Any, Optional

# Session timeout: 15 minutes (900 seconds) of inactivity
SESSION_TIMEOUT_SECONDS = 15 * 60

class MerchantCartSession:
    _sessions: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def get_session(cls, store_id: int) -> Dict[str, Any]:
        """
        Retrieves or initializes an active session for the store_id.
        Applies lazy expiry: if session inactivity > 15 minutes, clears and resets it.
        """
        now = time.time()
        session = cls._sessions.get(store_id)

        if session:
            # Check 15-minute inactivity timeout
            if now - session.get('last_active', 0) > SESSION_TIMEOUT_SECONDS:
                cls.clear_session(store_id)
                session = None

        if not session:
            session = {
                "session_id": str(uuid.uuid4()),
                "store_id": store_id,
                "cart": [],
                "last_referenced_item": None,
                "last_referenced_customer": None,
                "created_at": now,
                "last_active": now
            }
            cls._sessions[store_id] = session

        session['last_active'] = now
        return session

    @classmethod
    def update_cart(cls, store_id: int, items: list) -> Dict[str, Any]:
        session = cls.get_session(store_id)
        session['cart'] = items
        session['last_active'] = time.time()
        return session

    @classmethod
    def set_last_item(cls, store_id: int, item_data: Dict[str, Any]):
        session = cls.get_session(store_id)
        session['last_referenced_item'] = item_data
        session['last_active'] = time.time()

    @classmethod
    def set_last_customer(cls, store_id: int, customer_data: Dict[str, Any]):
        session = cls.get_session(store_id)
        session['last_referenced_customer'] = customer_data
        session['last_active'] = time.time()

    @classmethod
    def resolve_reference(cls, store_id: int, ref_type: str = "item") -> Optional[Dict[str, Any]]:
        """
        Resolves a spoken reference like "add two more" or "change to 3 kg" to the last referenced item or customer.
        Applies lazy expiry check. If session expired or reference is missing, returns None.
        """
        now = time.time()
        session = cls._sessions.get(store_id)
        if not session:
            return None

        if now - session.get('last_active', 0) > SESSION_TIMEOUT_SECONDS:
            cls.clear_session(store_id)
            return None

        session['last_active'] = now
        if ref_type == "item":
            return session.get('last_referenced_item')
        elif ref_type == "customer":
            return session.get('last_referenced_customer')
        return None

    @classmethod
    def get_context(cls, store_id: int) -> Dict[str, Any]:
        """
        Returns structured context for passing to AIOrchestrationService.
        """
        session = cls.get_session(store_id)
        return {
            "session_id": session.get("session_id"),
            "last_referenced_item": session.get("last_referenced_item"),
            "last_referenced_customer": session.get("last_referenced_customer"),
            "cart_count": len(session.get("cart", []))
        }

    @classmethod
    def clear_session(cls, store_id: int):
        if store_id in cls._sessions:
            del cls._sessions[store_id]
