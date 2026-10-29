"""REST API handlers coordinating auth and database operations."""

from examples.sample_project.auth import TokenManager, User
from examples.sample_project.database import DatabasePool


class OrderService:
    """Business service handling customer orders."""

    def __init__(self, db: DatabasePool, tokens: TokenManager) -> None:
        self.db = db
        self.tokens = tokens

    def place_order(self, auth_token: str, item_id: str, quantity: int) -> dict:
        """Place an order after verifying credentials."""
        user_id = self.tokens.verify_token(auth_token)
        if not user_id:
            raise PermissionError("Invalid authentication token.")
        
        self.db.execute_query(
            "INSERT INTO orders (user_id, item_id, quantity) VALUES (:u, :i, :q)",
            {"u": user_id, "i": item_id, "q": quantity},
        )
        return {"order_id": "ord-9988", "status": "confirmed"}
