<script lang="ts">
	export let values: number[] = [];
	export let timestamps: string[] = [];
	export let height = 80;

	const VW = 500;
	const pad = { top: 12, right: 12, bottom: 22, left: 44 };

	$: plotW = VW - pad.left - pad.right;
	$: plotH = height - pad.top - pad.bottom;

	$: min = values.length ? Math.min(...values) : 0;
	$: max = values.length ? Math.max(...values) : 100;
	$: range = max - min || 1;
	$: avg = values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;

	$: lineColor = avg < 150 ? '#34d399' : avg < 400 ? '#fbbf24' : '#f87171';

	$: pts = values.map((v, i) => ({
		x: pad.left + (i / Math.max(values.length - 1, 1)) * plotW,
		y: pad.top + (1 - (v - min) / range) * plotH,
		v,
		ts: timestamps[i] ?? null
	}));

	function smoothPath(points: { x: number; y: number }[]): string {
		if (points.length < 2) return '';
		let d = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
		for (let i = 1; i < points.length; i++) {
			const cpx = ((points[i - 1].x + points[i].x) / 2).toFixed(1);
			d += ` C ${cpx},${points[i - 1].y.toFixed(1)} ${cpx},${points[i].y.toFixed(1)} ${points[i].x.toFixed(1)},${points[i].y.toFixed(1)}`;
		}
		return d;
	}

	$: linePath = smoothPath(pts);
	$: baseline = pad.top + plotH;
	$: areaPath =
		pts.length >= 2
			? `${linePath} L ${pts[pts.length - 1].x.toFixed(1)},${baseline} L ${pts[0].x.toFixed(1)},${baseline} Z`
			: '';

	$: gridLines = [0.2, 0.5, 0.8].map((p) => ({
		y: pad.top + p * plotH,
		label: Math.round(max - p * range)
	}));

	$: xLabels = (() => {
		if (!timestamps.length || pts.length < 2) return [];
		const count = Math.min(5, pts.length);
		return Array.from({ length: count }, (_, i) => {
			const idx = Math.round((i / (count - 1)) * (pts.length - 1));
			const ts = timestamps[idx];
			if (!ts) return null;
			const d = new Date(ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z');
			return {
				x: pts[idx].x,
				label: d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
			};
		}).filter(Boolean) as { x: number; label: string }[];
	})();

	const gradId = `sg-${Math.random().toString(36).slice(2, 7)}`;

	// ── Hover ──────────────────────────────────────────────────────────────
	let svgEl: SVGSVGElement;
	let hovered: { x: number; y: number; v: number; label: string } | null = null;

	function toUtcDate(s: string): Date {
		return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');
	}

	function onMouseMove(e: MouseEvent) {
		if (!pts.length) return;
		const rect = svgEl.getBoundingClientRect();
		const svgX = ((e.clientX - rect.left) / rect.width) * VW;

		// Point le plus proche
		let best = 0;
		let bestDist = Infinity;
		for (let i = 0; i < pts.length; i++) {
			const d = Math.abs(pts[i].x - svgX);
			if (d < bestDist) {
				bestDist = d;
				best = i;
			}
		}

		const p = pts[best];
		const ts = p.ts
			? toUtcDate(p.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
			: '';
		hovered = { x: p.x, y: p.y, v: p.v, label: ts };
	}

	function onMouseLeave() {
		hovered = null;
	}

	// Position du tooltip : reste dans les bornes du SVG
	function tooltipX(x: number): number {
		const tw = 90;
		if (x + tw / 2 > VW - pad.right) return VW - pad.right - tw - 4;
		if (x - tw / 2 < pad.left) return pad.left + 4;
		return x - tw / 2;
	}
</script>

<svg
	bind:this={svgEl}
	viewBox="0 0 {VW} {height}"
	width="100%"
	{height}
	class="overflow-visible cursor-crosshair"
	aria-hidden="true"
	on:mousemove={onMouseMove}
	on:mouseleave={onMouseLeave}
>
	<defs>
		<linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
			<stop offset="0%" stop-color={lineColor} stop-opacity="0.3" />
			<stop offset="100%" stop-color={lineColor} stop-opacity="0" />
		</linearGradient>
	</defs>

	<!-- Grille Y -->
	{#each gridLines as gl}
		<line
			x1={pad.left}
			y1={gl.y}
			x2={VW - pad.right}
			y2={gl.y}
			stroke="rgba(148,163,184,0.12)"
			stroke-width="1"
			stroke-dasharray="4 4"
		/>
		<text
			x={pad.left - 7}
			y={gl.y + 4}
			text-anchor="end"
			fill="rgba(148,163,184,0.45)"
			font-size="10"
			font-family="monospace">{gl.label}</text
		>
	{/each}

	<!-- Baseline -->
	<line
		x1={pad.left}
		y1={baseline}
		x2={VW - pad.right}
		y2={baseline}
		stroke="rgba(148,163,184,0.2)"
		stroke-width="1"
	/>

	<!-- Labels Y min/max -->
	<text
		x={pad.left - 7}
		y={pad.top + 4}
		text-anchor="end"
		fill="rgba(148,163,184,0.45)"
		font-size="10"
		font-family="monospace">{max}</text
	>
	<text
		x={pad.left - 7}
		y={baseline + 1}
		text-anchor="end"
		fill="rgba(148,163,184,0.45)"
		font-size="10"
		font-family="monospace">{min}</text
	>

	<!-- Unité ms -->
	<text
		x={VW - pad.right}
		y={pad.top - 2}
		text-anchor="end"
		fill="rgba(148,163,184,0.3)"
		font-size="9"
		font-family="monospace">ms</text
	>

	<!-- Labels X heure -->
	{#each xLabels as xl}
		<line
			x1={xl.x}
			y1={baseline}
			x2={xl.x}
			y2={baseline + 4}
			stroke="rgba(148,163,184,0.2)"
			stroke-width="1"
		/>
		<text
			x={xl.x}
			y={baseline + 14}
			text-anchor="middle"
			fill="rgba(148,163,184,0.45)"
			font-size="9"
			font-family="monospace">{xl.label}</text
		>
	{/each}

	{#if pts.length >= 2}
		<path d={areaPath} fill="url(#{gradId})" />
		<path
			d={linePath}
			fill="none"
			stroke={lineColor}
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		<circle cx={pts[0].x} cy={pts[0].y} r="2.5" fill={lineColor} opacity="0.5" />
		<circle
			cx={pts[pts.length - 1].x}
			cy={pts[pts.length - 1].y}
			r="4"
			fill={lineColor}
			opacity="0.15"
		/>
		<circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="2.5" fill={lineColor} />
	{:else if pts.length === 1}
		<circle cx={pts[0].x} cy={pts[0].y} r="3" fill={lineColor} />
	{:else}
		<text
			x={VW / 2}
			y={height / 2 + 4}
			text-anchor="middle"
			fill="rgba(148,163,184,0.3)"
			font-size="12">Pas encore de données</text
		>
	{/if}

	<!-- ── Hover overlay ─────────────────────────────────────────── -->
	{#if hovered}
		<!-- Ligne verticale -->
		<line
			x1={hovered.x}
			y1={pad.top}
			x2={hovered.x}
			y2={baseline}
			stroke="rgba(148,163,184,0.35)"
			stroke-width="1"
			stroke-dasharray="3 3"
		/>

		<!-- Point surligné -->
		<circle cx={hovered.x} cy={hovered.y} r="5" fill={lineColor} opacity="0.2" />
		<circle cx={hovered.x} cy={hovered.y} r="3" fill={lineColor} />

		<!-- Tooltip -->
		{@const tx = tooltipX(hovered.x)}
		{@const ty = Math.max(pad.top, hovered.y - 36)}
		<rect
			x={tx}
			y={ty}
			width="90"
			height="26"
			rx="5"
			fill="#1e293b"
			fill-opacity="0.75"
			stroke="rgba(148,163,184,0.2)"
			stroke-width="1"
		/>
		<text x={tx + 8} y={ty + 10} fill="rgba(148,163,184,0.6)" font-size="9" font-family="monospace">
			{hovered.label}
		</text>
		<text
			x={tx + 8}
			y={ty + 21}
			fill={lineColor}
			font-size="10"
			font-weight="600"
			font-family="monospace"
		>
			{hovered.v} ms
		</text>
	{/if}
</svg>
