from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import jwt
from jwt import PyJWK


class TokenVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class OidcClaims:
    issuer: str
    subject: str
    audience: str | list[str]
    expires_at: int
    email: str | None = None


class JwtVerifier:
    """Verifies provider-neutral OIDC access tokens against an injected JWKS document."""

    def __init__(self, *, issuer: str, audience: str, jwks: Mapping[str, Any]):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        keys = jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("JWKS must contain at least one key")
        self._keys = {
            str(item["kid"]): PyJWK.from_dict(item).key
            for item in keys
            if isinstance(item, dict) and "kid" in item
        }

    def verify(self, token: str) -> OidcClaims:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in {"RS256", "ES256"}:
                raise TokenVerificationError("unsupported token algorithm")
            key = self._keys.get(str(header.get("kid")))
            if key is None:
                raise TokenVerificationError("unknown signing key")
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = claims.get("sub")
            if not isinstance(subject, str) or not subject:
                raise TokenVerificationError("invalid subject")
            audience = claims["aud"]
            if not isinstance(audience, str | list):
                raise TokenVerificationError("invalid audience")
            return OidcClaims(
                issuer=str(claims["iss"]),
                subject=subject,
                audience=audience,
                expires_at=int(claims["exp"]),
                email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            )
        except TokenVerificationError:
            raise
        except jwt.PyJWTError as exc:
            raise TokenVerificationError("token verification failed") from exc


def load_oidc_jwks(
    *, issuer: str, jwks_url: str | None, discovery_url: str | None
) -> Mapping[str, Any]:
    """Load OIDC metadata with an issuer-bound HTTPS allowlist."""
    issuer_url = urlparse(issuer)
    if issuer_url.scheme != "https" or not issuer_url.hostname:
        raise ValueError("OIDC issuer must be HTTPS")
    selected = jwks_url
    if selected is None:
        metadata_url = discovery_url or f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        metadata = _read_oidc_json(metadata_url, allowed_host=issuer_url.hostname)
        candidate = metadata.get("jwks_uri")
        if not isinstance(candidate, str):
            raise ValueError("OIDC discovery did not provide jwks_uri")
        selected = candidate
    return _read_oidc_json(selected, allowed_host=issuer_url.hostname)


def _read_oidc_json(url: str, *, allowed_host: str) -> Mapping[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host or parsed.username:
        raise ValueError("OIDC endpoint must be HTTPS and use the issuer host")
    with urlopen(url, timeout=5) as response:  # noqa: S310 - URL is constrained above
        if response.status != 200 or (response.length is not None and response.length > 1_000_000):
            raise ValueError("OIDC endpoint returned an invalid response")
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("OIDC response must be an object")
    return value
