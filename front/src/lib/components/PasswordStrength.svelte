<script lang="ts">
	export let password: string = '';
	export let valid = false;

	let checks = { length: false, uppercase: false, number: false, symbol: false };

	$: {
		checks = {
			length: password.length >= 8,
			uppercase: /[A-Z]/.test(password),
			number: /[0-9]/.test(password),
			symbol: /[^A-Za-z0-9]/.test(password)
		};
		valid = Object.values(checks).every(Boolean);
	}

	const rules = [
		{ key: 'length', label: '8 caractères minimum' },
		{ key: 'uppercase', label: '1 lettre majuscule' },
		{ key: 'number', label: '1 chiffre' },
		{ key: 'symbol', label: '1 symbole (ex: !@#$)' }
	] as const;
</script>

<ul class="flex flex-col gap-1 mt-1">
	{#each rules as rule}
		<li
			class="flex items-center gap-1.5 text-xs {checks[rule.key]
				? 'text-emerald-600'
				: 'text-slate-400'}"
		>
			{#if checks[rule.key]}
				<svg
					class="w-3.5 h-3.5 shrink-0"
					fill="none"
					stroke="currentColor"
					stroke-width="2.5"
					viewBox="0 0 24 24"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
				</svg>
			{:else}
				<svg
					class="w-3.5 h-3.5 shrink-0"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					viewBox="0 0 24 24"
				>
					<circle cx="12" cy="12" r="9" />
				</svg>
			{/if}
			{rule.label}
		</li>
	{/each}
</ul>
