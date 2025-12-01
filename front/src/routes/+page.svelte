<script lang="ts">
	import { monitors } from '$lib/stores/monitors';
	import MonitorCard from '$lib/components/MonitorCard.svelte';
	import { onMount } from 'svelte';

	let refreshing = false;

	// 🔥 FAUSSES DONNÉES — ton futur backend renverra ça
	const fakeData = [
		{
			name: 'Backend API',
			status: 'up',
			type: 'API',
			latency: 121,
			history: [120, 125, 118, 130, 121]
		},
		{
			name: 'Frontend',
			status: 'down',
			type: 'Website',
			latency: null,
			history: [120, 125, 118, 130, 121]
		},
		{
			name: 'Database',
			status: 'checking',
			type: 'DB',
			latency: null,
			history: [120, 125, 118, 130, 121]
		},
		{
			name: 'Auth Service',
			status: 'up',
			type: 'Service',
			latency: 98,
			history: [120, 125, 118, 130, 121]
		}
	];

	// 🟦 Simulation d’un fetch réseau mais sans backend
	async function fetchStatus() {
		refreshing = true;

		// Petite pause pour simuler l'appel API
		await new Promise((resolve) => setTimeout(resolve, 600));

		// 🔄 On génère du mouvement (latence random & changements de status)
		const updated = fakeData.map((m) => {
			// latence qui varie légèrement
			let latency = m.latency;
			if (latency !== null) {
				latency = latency + Math.round((Math.random() - 0.5) * 20);
				latency = Math.max(20, latency); // min 20ms
			}

			// On simule de temps en temps un crash ou un up
			let status = m.status;
			if (Math.random() < 0.07) {
				// 7% de chance de changer
				const all = ['up', 'down', 'checking'];
				status = all[Math.floor(Math.random() * all.length)];
			}

			return {
				...m,
				status,
				latency
			};
		});

		monitors.set(updated);

		refreshing = false;
	}

	onMount(() => {
		fetchStatus(); // charge au démarrage
		const interval = setInterval(fetchStatus, 8000); // refresh toutes les 8 sec
		return () => clearInterval(interval);
	});
</script>

<!-- 🔄 Indicateur en haut -->
{#if refreshing}
	<div class="text-blue-300 text-sm mb-2 animate-pulse pl-6">🔄 Refreshing status…</div>
{/if}

<!-- 🧩 Les cards -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6">
	{#each $monitors as m}
		<MonitorCard {...m} />
	{/each}
</div>
