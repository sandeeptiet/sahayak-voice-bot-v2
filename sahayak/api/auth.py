"""Cognito access-token authentication plus online revocation validation."""
from dataclasses import dataclass
import httpx
import jwt
from fastapi import HTTPException
from .config import Settings


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    groups: frozenset[str]


def validate_claims(token: str, key, settings: Settings) -> Principal:
    claims = jwt.decode(token, key, algorithms=["RS256"], issuer=settings.issuer,
                        options={"require": ["exp", "iat", "sub", "iss", "client_id", "token_use"],
                                 "verify_aud": False})
    if claims["token_use"] != "access" or claims["client_id"] != settings.cognito_client_id:
        raise jwt.InvalidTokenError("Wrong token purpose/client")
    if "openid" not in str(claims.get("scope", "")).split():
        raise jwt.InvalidTokenError("Missing openid scope")
    groups = claims.get("cognito:groups", [])
    if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
        raise jwt.InvalidTokenError("Invalid groups")
    return Principal(claims["iss"], claims["sub"], frozenset(groups))


class CognitoVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.keys = jwt.PyJWKClient(f"{settings.issuer}/.well-known/jwks.json", timeout=10, lifespan=300)
        self.http = httpx.Client(timeout=10, follow_redirects=False)

    def close(self):
        self.http.close()

    def verify(self, token: str) -> Principal:
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            principal = validate_claims(token, key, self.settings)
        except jwt.PyJWKClientConnectionError:
            raise HTTPException(503, "Sign-in verification is temporarily unavailable") from None
        except jwt.PyJWTError:
            raise HTTPException(401, "Please sign in again") from None
        # Offline JWT validation alone cannot detect revoked/disabled sessions.
        try:
            response = self.http.get(f"{self.settings.cognito_domain}/oauth2/userInfo",
                                     headers={"Authorization": f"Bearer {token}"})
            if response.status_code in (400, 401, 403):
                raise HTTPException(401, "Please sign in again")
            response.raise_for_status()
            if response.json().get("sub") != principal.subject:
                raise HTTPException(401, "Please sign in again")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Sign-in verification is temporarily unavailable") from None
        return principal
