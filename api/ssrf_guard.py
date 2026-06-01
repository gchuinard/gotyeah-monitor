"""Garde anti-SSRF partagée : refuse les URL résolvant vers le réseau interne.

Module dédié pour être importable à la fois par la boucle de monitoring (main.py,
checks de monitors) et par l'alerting (notifications.py, webhooks) sans import circulaire.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_resolves_to_blocked_ip(hostname: str, port: int) -> bool:
    """True si l'hôte résout (même partiellement) vers une IP interne/privée."""
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except Exception:
        return True  # résolution impossible -> on bloque par précaution
    return any(_ip_is_blocked(info[4][0]) for info in infos)


async def url_is_safe(url: str) -> bool:
    """Refuse une URL ciblant le réseau interne (loopback, RFC1918, link-local /
    métadonnées cloud, etc.). Résolution DNS faite au moment de l'appel (anti-rebinding)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_event_loop()
    return not await loop.run_in_executor(
        None, _host_resolves_to_blocked_ip, hostname, port
    )
