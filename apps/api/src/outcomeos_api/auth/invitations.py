import hashlib
import hmac
import secrets


class InvitationTokenHasher:
    """Generates invitation tokens that are shown once and stored only as keyed digests."""

    def __init__(self, pepper: str):
        if len(pepper) < 16:
            raise ValueError("invitation pepper must be at least 16 characters")
        self._pepper = pepper.encode()

    def generate(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        return token, self.digest(token)

    def digest(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode(), hashlib.sha256).hexdigest()

    def verify(self, token: str, digest: str) -> bool:
        return hmac.compare_digest(self.digest(token), digest)
