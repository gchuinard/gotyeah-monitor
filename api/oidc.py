"""Connexion OIDC (bouton « Se connecter avec Pocket ID ») À CÔTÉ du formulaire
email/mot de passe — pas à la place.

Flux : Authorization Code + PKCE, piloté par le backend, qui émet ENSUITE le même JWT
applicatif que le login classique (voir auth.create_access_token). Aucune dépendance
nouvelle : échange de code via httpx, validation de l'id_token via PyJWT (PyJWKClient),
tous deux déjà présents.

État (state/nonce/code_verifier) transporté dans un cookie signé (HS256, SECRET_KEY),
HttpOnly + Secure + SameSite=Lax, court : flux sans stockage serveur. Les endpoints
/login et /callback sont des navigations top-level (pas de fetch) -> pas de CORS ;
/status est un GET public lu par le SPA (couvert par le CORS existant).
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient, PyJWTError
from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import team_access
from auth import SECRET_KEY, ALGORITHM, create_access_token, get_user_by_email, get_password_hash
from rate_limit import limiter


# --- Configuration (env). OIDC actif seulement si les 4 valeurs clés sont présentes. ---
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "").rstrip("/")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "")
OIDC_ALLOW_SIGNUP = os.getenv("OIDC_ALLOW_SIGNUP", "true").lower() == "true"
OIDC_BUTTON_LABEL = os.getenv("OIDC_BUTTON_LABEL", "Se connecter avec Pocket ID")
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid email profile")
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# FRONTEND_URL est requis : sans lui, la redirection de retour serait relative et
# atterrirait sur l'origine de l'API (login cassé). On désactive donc OIDC plutôt que
# d'exposer un bouton qui mène à une impasse.
OIDC_ENABLED = bool(
    OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET and OIDC_REDIRECT_URI and FRONTEND_URL
)

# Algos de signature acceptés pour l'id_token : ASYMÉTRIQUES uniquement (jamais HS*),
# pour écarter toute confusion d'algorithme même si la discovery en annonçait un.
_SAFE_ID_TOKEN_ALGS = {
    "RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512",
}

# Cookie d'état : court, à portée limitée au callback.
_STATE_COOKIE = "oidc_state"
_STATE_TTL_SECONDS = 600

router = APIRouter(prefix="/auth/oidc", tags=["auth"])

# Caches process (discovery + client JWKS). Idempotents : une éventuelle course au
# premier appel ne fait que refetch, sans effet de bord.
_discovery: Optional[dict] = None
_jwks_client: Optional[PyJWKClient] = None


async def _get_discovery() -> dict:
    global _discovery
    if _discovery is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{OIDC_ISSUER}/.well-known/openid-configuration", timeout=10.0
            )
            resp.raise_for_status()
            _discovery = resp.json()
    return _discovery


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(jwks_uri)
    return _jwks_client


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def _frontend_redirect(fragment: str = "", query: str = "") -> RedirectResponse:
    """Redirige le navigateur vers la page de login du SPA. Le JWT voyage dans le
    FRAGMENT (#session=...) : jamais envoyé au serveur ni journalisé (cohérent avec le
    reste de l'app). Les erreurs voyagent en query (?sso_error=..., non sensible)."""
    base = f"{FRONTEND_URL or ''}/login"
    return RedirectResponse(
        url=f"{base}{query}{fragment}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/status")
async def oidc_status() -> dict:
    """Lu par le SPA pour afficher (ou non) le bouton et son libellé."""
    return {
        "enabled": OIDC_ENABLED,
        "label": OIDC_BUTTON_LABEL if OIDC_ENABLED else None,
    }


@router.get("/login")
@limiter.limit("10/minute")
async def oidc_login(request: Request) -> RedirectResponse:
    if not OIDC_ENABLED:
        return _frontend_redirect(query="?sso_error=disabled")

    disc = await _get_discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()

    # État signé (non chiffré mais HttpOnly + Secure + TLS) : suffisant pour du
    # state/nonce/PKCE, et vérifiable côté callback sans stockage serveur.
    state_jwt = jwt.encode(
        {
            "state": state,
            "nonce": nonce,
            "cv": verifier,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    params = {
        "response_type": "code",
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": OIDC_REDIRECT_URI,
        "scope": OIDC_SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    resp = RedirectResponse(
        url=f"{disc['authorization_endpoint']}?{urlencode(params)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    resp.set_cookie(
        _STATE_COOKIE,
        state_jwt,
        max_age=_STATE_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth/oidc",
    )
    return resp


@router.get("/callback")
@limiter.limit("10/minute")
async def oidc_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if not OIDC_ENABLED:
        return _frontend_redirect(query="?sso_error=disabled")

    def _fail(reason: str) -> RedirectResponse:
        r = _frontend_redirect(query=f"?sso_error={reason}")
        r.delete_cookie(_STATE_COOKIE, path="/auth/oidc")
        return r

    # Le fournisseur peut renvoyer une erreur (refus, etc.).
    if request.query_params.get("error"):
        return _fail("provider")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    raw_state = request.cookies.get(_STATE_COOKIE)
    if not code or not state or not raw_state:
        return _fail("state")

    # 1) Vérifier l'état (CSRF) depuis le cookie signé.
    try:
        st = jwt.decode(raw_state, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return _fail("state")
    if not secrets.compare_digest(st.get("state", ""), state):
        return _fail("state")

    disc = await _get_discovery()

    # 2) Échanger le code contre les tokens (avec le code_verifier PKCE).
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                disc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": OIDC_REDIRECT_URI,
                    "client_id": OIDC_CLIENT_ID,
                    "client_secret": OIDC_CLIENT_SECRET,
                    "code_verifier": st.get("cv", ""),
                },
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
        token_resp.raise_for_status()
        id_token = token_resp.json().get("id_token")
        if not id_token:
            return _fail("token")
    except (httpx.HTTPError, ValueError):
        return _fail("token")

    # 3) Valider l'id_token (signature via JWKS, iss/aud/exp, puis nonce).
    try:
        jwks = _get_jwks_client(disc["jwks_uri"])
        signing_key = await run_in_threadpool(jwks.get_signing_key_from_jwt, id_token)
        algs = [
            a
            for a in disc.get("id_token_signing_alg_values_supported", [])
            if a in _SAFE_ID_TOKEN_ALGS
        ] or ["RS256"]
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=algs,
            audience=OIDC_CLIENT_ID,
            issuer=disc["issuer"],
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    except PyJWTError:
        return _fail("idtoken")
    if not secrets.compare_digest(claims.get("nonce", ""), st.get("nonce", "")):
        return _fail("nonce")

    email = (claims.get("email") or "").strip().lower()
    if not email:
        return _fail("noemail")
    # email_verified : on refuse SEULEMENT si explicitement False (Pocket ID le pose à
    # true ; un fournisseur qui l'omet n'est pas bloqué).
    if claims.get("email_verified") is False:
        return _fail("unverified")

    # 4) Lier au compte existant (par email) ou provisionner.
    user = await get_user_by_email(db, email)
    if user is None:
        if not OIDC_ALLOW_SIGNUP:
            return _fail("nosignup")
        # Compte issu d'un IdP de confiance : email déjà vérifié. Mot de passe local
        # aléatoire inutilisable (connexion par bouton ; « mot de passe oublié » permet
        # d'en définir un plus tard). Équipe personnelle comme au register classique.
        user = models.User(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        await team_access.create_team(db, "Mon espace", user.id)
        await db.commit()
    elif not user.is_verified:
        # L'IdP atteste l'email -> on peut confirmer un compte resté non vérifié.
        user.is_verified = True
        await db.commit()

    # 5) Émettre le JWT applicatif (identique au login mot de passe) et rendre la main
    #    au SPA via le fragment.
    access_token = create_access_token(data={"sub": str(user.id), "tv": user.token_version})
    resp = _frontend_redirect(fragment=f"#session={access_token}")
    resp.delete_cookie(_STATE_COOKIE, path="/auth/oidc")
    return resp
