"""Limiteur de débit partagé (anti brute-force / abus d'envoi d'emails).

Défini dans son propre module pour éviter un import circulaire entre main.py
(qui câble le handler) et auth.py (qui décore les routes).
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _client_ip(request: Request) -> str:
    # Derrière Cloudflare, l'IP réelle du client est dans CF-Connecting-IP : CF
    # écrase cet en-tête à chaque requête (non falsifiable par le client), tant que
    # l'origine n'accepte QUE le trafic CF (Authenticated Origin Pulls / firewall IP
    # CF — cf. ops/cloudflare-origin.conf). On NE lit PAS X-Forwarded-For[0] : sa
    # valeur la plus à gauche est fournie par le client, donc spoofable (CWE-348) —
    # le rate-limit serait contournable même au travers de CF.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    # Hors CF (dev local en direct) : pas d'en-tête de proxy fiable → IP du socket.
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip)
