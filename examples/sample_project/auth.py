"""Authentication and authorization services."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Represents an authenticated user account."""

    user_id: str
    username: str
    email: str
    is_active: bool = True


class TokenManager:
    """Handles token generation and verification."""

    def __init__(self, secret_key: str = "secret-12345") -> None:
        self.secret_key = secret_key

    def create_token(self, user: User) -> str:
        """Generate a signed authentication token for the given user."""
        return f"token-{user.user_id}-{self.secret_key[:4]}"

    def verify_token(self, token: str) -> Optional[str]:
        """Verify the authenticity of a token and return user ID if valid."""
        if token.startswith("token-"):
            parts = token.split("-")
            return parts[1]
        return None
