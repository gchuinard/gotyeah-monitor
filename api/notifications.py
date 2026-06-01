"""Moteur d'alerting : décision (transitions d'état + SSL) et envoi (email + webhook).

La décision (evaluate_alerts) met à jour l'état anti-flapping sur les monitors et
renvoie une liste d'alertes. L'envoi (dispatch_alerts) émet email + webhook ; les
drapeaux "déjà notifié" ne sont posés qu'en cas de succès de l'email, pour réessayer
au cycle suivant si l'envoi a échoué.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

import models
from ssrf_guard import url_is_safe
from mail_service import (
    send_monitor_down_email,
    send_monitor_up_email,
    send_ssl_expiry_email,
)

logger = logging.getLogger("monitor")

# Nombre d'échecs consécutifs avant de déclarer DOWN (anti-flapping).
ALERT_FAILURE_THRESHOLD = 2
# Paliers d'alerte avant expiration du certificat SSL, en jours.
SSL_ALERT_THRESHOLDS = (1, 7, 14, 30)


def _ssl_level(days_left: int) -> Optional[int]:
    """Palier d'alerte courant (None si rien à alerter). Niveau 0 = certificat expiré,
    pour qu'une alerte distincte parte aussi au moment réel de l'expiration."""
    if days_left < 0:
        return 0
    for t in sorted(SSL_ALERT_THRESHOLDS):
        if days_left <= t:
            return t
    return None


class _Alert:
    def __init__(self, monitor: "models.Monitor", kind: str, **data):
        self.user = monitor.user
        self.monitor_name = monitor.name
        self.kind = kind  # 'down' | 'up' | 'ssl'
        self.data = data
        self._monitor = monitor

    def mark_sent(self) -> None:
        m = self._monitor
        if self.kind == "down":
            m.down_alert_sent = True
        elif self.kind == "up":
            m.down_alert_sent = False
            m.down_since = None
        elif self.kind == "ssl":
            m.ssl_alert_level = self.data["level"]


def evaluate_alerts(monitors: List["models.Monitor"], now: datetime) -> List[_Alert]:
    """Met à jour l'état d'alerting des monitors (in place) et renvoie les alertes à envoyer.
    À appeler APRÈS application des résultats de probe (monitor.status est le statut courant)."""
    alerts: List[_Alert] = []
    for m in monitors:
        # Compteur d'échecs consécutifs
        if m.status == "down":
            if m.consecutive_failures == 0:
                m.down_since = now
            m.consecutive_failures += 1
        else:
            m.consecutive_failures = 0

        # Pas de destinataire (monitor orphelin) -> rien à notifier
        if m.user is None:
            continue

        # Transition DOWN confirmée (seuil atteint, pas encore notifié)
        if (
            m.status == "down"
            and m.consecutive_failures >= ALERT_FAILURE_THRESHOLD
            and not m.down_alert_sent
        ):
            alerts.append(
                _Alert(m, "down", status_code=m.last_status_code, since=m.down_since)
            )
        # Rétablissement (on n'alerte que si on avait alerté la panne)
        elif m.status == "up" and m.down_alert_sent:
            alerts.append(_Alert(m, "up", since=m.down_since, now=now))

        # Expiration SSL
        expiry = m.ssl_expiry_at
        if expiry is not None:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            days_left = (expiry - now).days
            level = _ssl_level(days_left)
            if level is not None and m.ssl_alert_level != level:
                alerts.append(_Alert(m, "ssl", days_left=days_left, level=level))
            elif level is None and m.ssl_alert_level is not None:
                m.ssl_alert_level = None  # certificat renouvelé -> reset silencieux

    return alerts


def _alert_text(a: _Alert) -> str:
    if a.kind == "down":
        sc = a.data.get("status_code")
        reason = f"code HTTP {sc}" if sc is not None else "aucune réponse"
        return f"🔴 **{a.monitor_name}** est DOWN ({reason})."
    if a.kind == "up":
        return f"🟢 **{a.monitor_name}** est de nouveau UP."
    if a.kind == "ssl":
        d = a.data["days_left"]
        return f"⏳ Certificat SSL de **{a.monitor_name}** : {'expiré' if d < 0 else f'expire dans {d} j'}."
    return a.monitor_name


async def _send_webhook(client: httpx.AsyncClient, url: str, kind: Optional[str], text: str) -> None:
    kind = (kind or "generic").lower()
    if kind == "discord":
        await client.post(url, json={"content": text}, timeout=10.0)
    elif kind == "slack":
        await client.post(url, json={"text": text}, timeout=10.0)
    elif kind == "ntfy":
        await client.post(url, content=text.encode("utf-8"), timeout=10.0)
    else:  # generic JSON
        await client.post(url, json={"text": text}, timeout=10.0)


async def _send_one(client: httpx.AsyncClient, a: _Alert) -> None:
    user = a.user
    email_ok = False
    try:
        if a.kind == "down":
            await send_monitor_down_email(user.email, a.monitor_name, a.data["status_code"], a.data["since"])
        elif a.kind == "up":
            await send_monitor_up_email(user.email, a.monitor_name, a.data["since"], a.data["now"])
        elif a.kind == "ssl":
            await send_ssl_expiry_email(user.email, a.monitor_name, a.data["days_left"])
        email_ok = True
    except Exception:
        logger.exception("Échec envoi email d'alerte (%s / %s)", a.kind, a.monitor_name)

    # Webhook best-effort (n'influence pas le drapeau "déjà notifié")
    if user.alert_webhook_url:
        try:
            # Anti-SSRF : ne jamais POSTer vers une cible interne (même garde que les checks).
            if await url_is_safe(user.alert_webhook_url):
                await _send_webhook(client, user.alert_webhook_url, user.alert_webhook_kind, _alert_text(a))
            else:
                logger.warning("Webhook ignoré : URL vers une cible interne/non autorisée")
        except Exception:
            logger.exception("Échec envoi webhook d'alerte (%s / %s)", a.kind, a.monitor_name)

    # On ne pose le drapeau que si l'email est parti (sinon on réessaie au prochain cycle).
    if email_ok:
        a.mark_sent()


async def dispatch_alerts(client: httpx.AsyncClient, alerts: List[_Alert]) -> None:
    if not alerts:
        return
    await asyncio.gather(*[_send_one(client, a) for a in alerts])
