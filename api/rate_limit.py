"""Limiteur de débit partagé (anti brute-force / abus d'envoi d'emails).

Défini dans son propre module pour éviter un import circulaire entre main.py
(qui câble le handler) et auth.py (qui décore les routes).
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _client_ip(request: Request) -> str:
    # Derrière le reverse proxy (monitor_net), l'IP réelle est dans X-Forwarded-For.
    # Seul le proxy peut joindre le conteneur, donc on peut s'y fier ici.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip)
