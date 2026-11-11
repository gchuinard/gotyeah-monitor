"""Export « Copier pour diagnostic » : historique d'un monitor en Markdown prêt à coller.

Partagé par GET /monitors/{id}/diagnostic et le pont MCP. L'appelant a déjà vérifié
l'accès (require_monitor, readonly). Ne contient que des données de mesure : ni
destinataires, ni emails, ni webhook, ni token, ni mot-clé.
"""
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models

WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}
# Défaut global de la boucle (main.CHECK_INTERVAL_SECONDS ; import direct impossible : circulaire).
DEFAULT_INTERVAL_SECONDS = 600
PEAK_FACTOR = 3
# Nombre max de pics détaillés (les plus lents), pour borner la taille de l'export.
MAX_PEAKS_LISTED = 50


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> str:
    dt = _utc(dt)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else "—"


def _safe_url(url: str) -> str:
    """URL sans identifiants ni paramètres : une URL de monitor peut porter `user:pass@` ou
    un `?token=`, et l'export est fait pour sortir de l'app."""
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if p.port:
            host = f"{host}:{p.port}"
        masked = bool(p.username or p.password or p.query or p.fragment)
        clean = urlunsplit((p.scheme, host, p.path, "", ""))
        return clean + (" (identifiants/paramètres masqués)" if masked else "")
    except ValueError:
        return "(URL illisible)"


def _p95(values: List[int]) -> int:
    ordered = sorted(values)
    idx = max(0, -(-95 * len(ordered) // 100) - 1)  # rang « nearest-rank »
    return ordered[idx]


def _duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


async def build_diagnostic(db: AsyncSession, monitor: models.Monitor, window: str) -> str:
    now = datetime.now(timezone.utc)
    since = now - WINDOWS[window]

    res = await db.execute(
        select(models.MonitorCheck.checked_at, models.MonitorCheck.status, models.MonitorCheck.latency_ms)
        .where(
            models.MonitorCheck.monitor_id == monitor.id,
            models.MonitorCheck.checked_at >= since,
        )
        .order_by(models.MonitorCheck.checked_at.asc())
    )
    checks = res.all()
    latencies = [c.latency_ms for c in checks if c.latency_ms is not None]
    up = sum(1 for c in checks if c.status == "up")

    interval = monitor.check_interval_seconds
    lines = [
        f"# Diagnostic monitor : {monitor.name}",
        "",
        f"- URL : {_safe_url(monitor.url)}",
        f"- Type : {monitor.type}" + (f" (port {monitor.port})" if monitor.type == "port" and monitor.port else ""),
        f"- Intervalle : {interval} s" if interval else f"- Intervalle : {DEFAULT_INTERVAL_SECONDS} s (défaut)",
        f"- Seuil de latence : {monitor.latency_threshold_ms} ms"
        if monitor.latency_threshold_ms is not None
        else "- Seuil de latence : aucun",
        f"- Environnement : {monitor.environment or '—'}",
        f"- Fenêtre : {window} ({_iso(since)} → {_iso(now)})",
        f"- Généré le : {_iso(now)} (UTC)",
        "",
        "## Résumé",
        "",
        f"- Checks : {len(checks)} (up : {up}, down : {len(checks) - up})",
    ]

    median: Optional[float] = None
    if latencies:
        median = statistics.median(latencies)
        lines.append(
            f"- Latence : médiane {round(median)} ms, p95 {_p95(latencies)} ms, max {max(latencies)} ms"
        )
    else:
        lines.append("- Latence : aucune mesure")

    # Pics : au-dessus de 3× la médiane, ou du seuil s'il est défini.
    limits = []
    # Plancher à 1 ms : une médiane à 0 (connect TCP local tronqué par int()) reste un critère.
    peak_base = max(median, 1) if median is not None else None
    if peak_base is not None:
        limits.append(PEAK_FACTOR * peak_base)
    if monitor.latency_threshold_ms is not None:
        limits.append(monitor.latency_threshold_ms)
    peak_limit = min(limits) if limits else None
    peaks = (
        [c for c in checks if c.latency_ms is not None and c.latency_ms > peak_limit]
        if peak_limit is not None
        else []
    )
    criteria = []
    if peak_base is not None:
        criteria.append(f"> {PEAK_FACTOR}× la médiane ({round(PEAK_FACTOR * peak_base)} ms)")
    if monitor.latency_threshold_ms is not None:
        criteria.append(f"> seuil ({monitor.latency_threshold_ms} ms)")

    lines += ["", "## Pics de latence", ""]
    if peak_limit is None:
        lines.append("Pas de mesure de latence : pas de pic calculable.")
    elif not peaks:
        lines.append(f"Aucun pic (critère : {' ou '.join(criteria)}).")
    else:
        listed = sorted(peaks, key=lambda c: c.latency_ms, reverse=True)[:MAX_PEAKS_LISTED]
        listed.sort(key=lambda c: c.checked_at)
        lines.append(
            f"{len(peaks)} pic(s), critère : {' ou '.join(criteria)}."
            + (f" Les {MAX_PEAKS_LISTED} plus lents sont détaillés." if len(peaks) > MAX_PEAKS_LISTED else "")
        )
        lines.append(
            "Pour chaque pic, les autres monitors de la même équipe sondés au même tick "
            "(même `checked_at`) : s'ils sont lents aussi, le pic vient du tick ou du "
            "réseau de la sonde, pas du site."
        )
        lines.append("")
        neighbours: Dict[datetime, List[str]] = {}
        if monitor.team_id is not None:
            times = [c.checked_at for c in listed]
            nres = await db.execute(
                select(
                    models.MonitorCheck.checked_at,
                    models.Monitor.name,
                    models.MonitorCheck.status,
                    models.MonitorCheck.latency_ms,
                )
                .join(models.Monitor, models.Monitor.id == models.MonitorCheck.monitor_id)
                .where(
                    models.Monitor.team_id == monitor.team_id,
                    models.MonitorCheck.monitor_id != monitor.id,
                    models.MonitorCheck.checked_at.in_(times),
                )
                .order_by(models.Monitor.name.asc())
            )
            for row in nres.all():
                lat = f"{row.latency_ms} ms" if row.latency_ms is not None else "—"
                neighbours.setdefault(_utc(row.checked_at), []).append(f"{row.name} {lat} ({row.status})")
        lines += ["| checked_at (UTC) | latence | statut | autres monitors du même tick |", "|---|---|---|---|"]
        for c in listed:
            others = neighbours.get(_utc(c.checked_at))
            lines.append(
                f"| {_iso(c.checked_at)} | {c.latency_ms} ms | {c.status} | "
                f"{', '.join(others) if others else 'aucun'} |"
            )

    ires = await db.execute(
        select(models.Incident)
        .where(
            models.Incident.monitor_id == monitor.id,
            models.Incident.started_at < now,
            (models.Incident.ended_at.is_(None)) | (models.Incident.ended_at >= since),
        )
        .order_by(models.Incident.started_at.asc())
    )
    incidents = list(ires.scalars().all())
    lines += ["", "## Incidents de la fenêtre", ""]
    if not incidents:
        lines.append("Aucun.")
    else:
        lines += ["| début (UTC) | fin (UTC) | durée |", "|---|---|---|"]
        for inc in incidents:
            start, end = _utc(inc.started_at), _utc(inc.ended_at)
            dur = _duration(((end or now) - start).total_seconds())
            lines.append(f"| {_iso(start)} | {_iso(end) if end else 'en cours'} | {dur}{'' if end else ' (en cours)'} |")

    lines += ["", "## Checks bruts (TSV)", "", "```tsv", "checked_at\tstatus\tlatency_ms"]
    for c in checks:
        lines.append(f"{_iso(c.checked_at)}\t{c.status}\t{c.latency_ms if c.latency_ms is not None else ''}")
    lines += ["```", ""]
    return "\n".join(lines)
