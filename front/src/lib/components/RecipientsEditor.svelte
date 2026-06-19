<script lang="ts">
	import { apiFetch } from '$lib/utils/api';
	import { parseApiError } from '$lib/utils/errors';
	import { onMount } from 'svelte';

	// basePath = '/monitors/123' ou '/groups/4' ; teamId pour proposer les membres.
	export let basePath: string;
	export let teamId: number | null = null;
	export let readonly = false;
	// Style sombre (modal détail, fond slate-950) vs clair (modal groupes).
	export let dark = false;

	type Recipient = {
		id: number;
		email: string | null;
		member_user_id: number | null;
		member_email: string | null;
	};
	type Member = { id: number; user_id: number; email: string; role: string };

	let recipients: Recipient[] = [];
	let members: Member[] = [];
	let loaded = false;
	let newEmail = '';
	let newMemberId = '';
	let error: string | null = null;
	let adding = false;

	const fieldClass = dark ? 'field-dark' : 'field';

	async function load() {
		try {
			const res = await apiFetch(`${basePath}/recipients`);
			if (res.ok) recipients = (await res.json()) as Recipient[];
		} catch {
			/* best-effort */
		} finally {
			loaded = true;
		}
		if (teamId != null) {
			try {
				const r = await apiFetch(`/teams/${teamId}/members`);
				if (r.ok) members = (await r.json()) as Member[];
			} catch {
				/* best-effort */
			}
		}
	}

	onMount(load);

	async function addEmail() {
		const email = newEmail.trim();
		if (!email) return;
		adding = true;
		error = null;
		try {
			const res = await apiFetch(`${basePath}/recipients`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email })
			});
			if (!res.ok) {
				error = await parseApiError(res, 'destinataire');
				return;
			}
			newEmail = '';
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			adding = false;
		}
	}

	async function addMember() {
		if (!newMemberId) return;
		adding = true;
		error = null;
		try {
			const res = await apiFetch(`${basePath}/recipients`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ member_user_id: Number(newMemberId) })
			});
			if (!res.ok) {
				error = await parseApiError(res, 'destinataire');
				return;
			}
			newMemberId = '';
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			adding = false;
		}
	}

	async function remove(id: number) {
		error = null;
		try {
			const res = await apiFetch(`${basePath}/recipients/${id}`, { method: 'DELETE' });
			if (res.ok || res.status === 204) await load();
			else error = await parseApiError(res, 'destinataire');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
		}
	}

	function label(r: Recipient): string {
		return r.member_email ?? r.email ?? '—';
	}

	$: existingMemberIds = new Set(
		recipients.filter((r) => r.member_user_id != null).map((r) => r.member_user_id)
	);
	$: availableMembers = members.filter((m) => !existingMemberIds.has(m.user_id));
	// Classes complètes (pas d'interpolation partielle : Tailwind JIT ne la verrait pas).
	$: muted = dark ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400';
	$: memberBadge = dark
		? 'px-1.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
		: 'px-1.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-600 border border-cyan-500/30';
	$: emailBadge = dark
		? 'px-1.5 py-0.5 rounded-md bg-slate-500/15 text-slate-400 border border-slate-500/30'
		: 'px-1.5 py-0.5 rounded-md bg-slate-500/15 text-slate-500 dark:text-slate-400 border border-slate-500/30';
	$: valueText = dark ? 'text-slate-200' : 'text-slate-700 dark:text-slate-200';
	$: removeBtn = dark
		? 'ml-auto text-rose-400 hover:text-rose-300'
		: 'ml-auto text-rose-500 hover:text-rose-400';
	$: errorText = dark ? 'text-xs text-rose-400' : 'text-xs text-rose-500';
</script>

<div class="flex flex-col gap-2">
	{#if !loaded}
		<p class="text-xs {muted}">Chargement…</p>
	{:else if recipients.length === 0}
		<p class="text-xs {muted}">
			Aucun destinataire. Sans destinataire configuré, les admins de l'équipe sont notifiés.
		</p>
	{:else}
		<div class="flex flex-col gap-1">
			{#each recipients as r (r.id)}
				<div class="flex items-center gap-2 text-xs">
					{#if r.member_user_id != null}
						<span class={memberBadge}>membre</span>
					{:else}
						<span class={emailBadge}>email</span>
					{/if}
					<span class={valueText}>{label(r)}</span>
					{#if !readonly}
						<button type="button" class={removeBtn} on:click={() => remove(r.id)}>retirer</button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	{#if !readonly}
		<div class="flex items-center gap-2">
			<input
				class="flex-1 {fieldClass} text-xs"
				type="email"
				bind:value={newEmail}
				placeholder="email@exemple.com"
			/>
			<button
				type="button"
				class="btn btn-sm btn-secondary"
				on:click={addEmail}
				disabled={adding || !newEmail.trim()}>Ajouter</button
			>
		</div>
		{#if availableMembers.length > 0}
			<div class="flex items-center gap-2">
				<select class="flex-1 {fieldClass} text-xs" bind:value={newMemberId}>
					<option value="">+ Ajouter un membre de l'équipe…</option>
					{#each availableMembers as m (m.id)}
						<option value={String(m.user_id)}>{m.email}</option>
					{/each}
				</select>
				<button
					type="button"
					class="btn btn-sm btn-secondary"
					on:click={addMember}
					disabled={adding || !newMemberId}>Ajouter</button
				>
			</div>
		{/if}
		{#if error}<p class={errorText}>{error}</p>{/if}
	{/if}
</div>
