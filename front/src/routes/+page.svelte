<script lang="ts">
	import { monitors, type CheckEntry, type MonitorCardData } from '$lib/stores/monitors';
	import { auth, clearAuth, type AuthState } from '$lib/stores/auth';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';
	import { apiFetch } from '$lib/utils/api';
	import { modal } from '$lib/actions/modal';
	import { groups, loadGroups } from '$lib/stores/groups';
	import { groupCollapse, toggleGroupCollapse } from '$lib/stores/groupCollapse';
	import {
		teams,
		activeTeamId,
		activeTeam,
		activeRole,
		canWrite,
		loadTeams,
		type TeamRole
	} from '$lib/stores/teams';
	import MonitorCard from '$lib/components/MonitorCard.svelte';
	import MonitorDetailModal from '$lib/components/MonitorDetailModal.svelte';
	import RecipientsEditor from '$lib/components/RecipientsEditor.svelte';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { goto, preloadCode } from '$app/navigation';
	import {
		sortMode,
		groupOrder,
		monitorOrder,
		applyManualOrder,
		SORT_OPTIONS,
		type SortMode
	} from '$lib/stores/sortPrefs';
	import { dndzone } from 'svelte-dnd-action';

	type MonitorFromApi = {
		id: number;
		name: string;
		url: string;
		type: string;
		status: string;
		last_latency_ms: number | null;
		last_checked_at: string | null;
		expected_status_code: number;
		last_status_code: number | null;
		ssl_expiry_at: string | null;
		uptime_24h: number | null;
		uptime_7d: number | null;
		uptime_30d: number | null;
		uptime_90d: number | null;
		check_interval_seconds: number | null;
		keyword: string | null;
		keyword_mode: 'present' | 'absent' | null;
		latency_threshold_ms: number | null;
		port: number | null;
		group_id: number | null;
		team_id: number | null;
		environment: string | null;
		is_public: boolean;
		in_maintenance: boolean;
		created_at: string;
	};

	let loading = false;
	let error: string | null = null;
	let authState: AuthState;
	let viewMode: 'grid' | 'list' = 'grid';
	let isAdmin = false;
	let openCardId: number | null = null;

	// Rôle dans l'équipe active : readonly => pas d'actions d'écriture.
	$: isReadonly = $activeRole === 'readonly';
	$: canEdit = canWrite($activeRole);

	function toggleCardDetails(id: number) {
		openCardId = openCardId === id ? null : id;
	}

	// Add monitor modal
	let showAdd = false;
	let addName = '';
	let addUrl = '';
	let addType = 'http';
	let addExpectedStatusCode = 200;
	let addCheckIntervalSeconds: number | null = null;
	let addKeyword = '';
	let addKeywordMode: 'present' | 'absent' = 'present';
	let addLatencyThresholdMs: number | null = null;
	let addPort: number | null = null;
	let addGroupId: number | null = null;
	let addEnvironment = '';
	let addIsPublic = false;
	let addSubmitting = false;
	let addError: string | null = null;

	// Filtre par environnement sur le dashboard.
	let envFilter = '';

	function openAdd(groupId: number | null = null) {
		addName = '';
		addUrl = '';
		addType = 'http';
		addExpectedStatusCode = 200;
		addCheckIntervalSeconds = null;
		addKeyword = '';
		addKeywordMode = 'present';
		addLatencyThresholdMs = null;
		addPort = null;
		addGroupId = groupId;
		addEnvironment = '';
		addIsPublic = false;
		addError = null;
		showAdd = true;
	}

	async function submitAdd() {
		const teamId = get(activeTeamId);
		if (teamId == null) {
			addError = 'Aucune équipe active. Crée une équipe dans ton profil.';
			return;
		}
		addSubmitting = true;
		addError = null;
		try {
			const res = await apiFetch('/monitors', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: addName,
					url: addUrl,
					type: addType,
					expected_status_code: addExpectedStatusCode,
					check_interval_seconds: addCheckIntervalSeconds || null,
					keyword: addType === 'http' && addKeyword.trim() ? addKeyword.trim() : null,
					keyword_mode: addKeywordMode,
					latency_threshold_ms: addLatencyThresholdMs || null,
					port: addType === 'port' ? addPort : null,
					group_id: addGroupId == null ? null : Number(addGroupId),
					environment: addEnvironment.trim() || null,
					is_public: addIsPublic,
					team_id: teamId
				})
			});
			if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
			showAdd = false;
			await fetchMonitors();
		} catch (e) {
			addError = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			addSubmitting = false;
		}
	}

	// ── Recherche + gestion des groupes (M2) ──────────────────────────────
	let search = '';
	let showGroups = false;
	let newGroupName = '';
	let groupActionError: string | null = null;
	let groupRecipientsOpen: number | null = null;

	async function assignGroup(monitorId, groupId) {
		const mon = $monitors.find((x) => x.id === monitorId);
		if (!mon) return;
		try {
			await apiFetch(`/monitors/${monitorId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: mon.name,
					url: mon.url,
					type: mon.type,
					expected_status_code: mon.expectedStatusCode,
					check_interval_seconds: mon.checkIntervalSeconds,
					keyword: mon.keyword,
					keyword_mode: mon.keywordMode ?? 'present',
					latency_threshold_ms: mon.latencyThresholdMs,
					port: mon.port,
					group_id: groupId,
					environment: mon.environment,
					is_public: mon.isPublic
				})
			});
			await fetchMonitors();
		} catch {
			/* ignore */
		}
	}

	async function createGroup() {
		const name = newGroupName.trim();
		if (!name) return;
		const teamId = get(activeTeamId);
		if (teamId == null) {
			groupActionError = 'Aucune équipe active.';
			return;
		}
		groupActionError = null;
		try {
			const res = await apiFetch('/groups', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name, team_id: teamId })
			});
			if (!res.ok) {
				groupActionError = await parseApiError(res, 'groupe');
				return;
			}
			newGroupName = '';
			await loadGroups(get(activeTeamId));
		} catch (e) {
			groupActionError = parseNetworkError(e, 'groupe');
		}
	}

	async function renameGroup(id: number, name: string) {
		const n = name.trim();
		if (!n) return;
		try {
			await apiFetch(`/groups/${id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: n })
			});
			await loadGroups(get(activeTeamId));
		} catch {
			/* ignore */
		}
	}

	async function deleteGroup(id: number) {
		try {
			await apiFetch(`/groups/${id}`, { method: 'DELETE' });
			await loadGroups(get(activeTeamId));
			await fetchMonitors();
		} catch {
			/* ignore */
		}
	}

	$: q = search.trim().toLowerCase();
	$: envOptions = Array.from(
		new Set($monitors.map((m) => m.environment).filter((e): e is string => !!e))
	).sort((a, b) => a.localeCompare(b, 'fr'));
	$: filteredMonitors = $monitors.filter((m) => {
		if (q && !(m.name.toLowerCase().includes(q) || m.url.toLowerCase().includes(q))) return false;
		if (envFilter && (m.environment ?? '') !== envFilter) return false;
		return true;
	});
	$: groupSections = [
		...$groups.map((g) => ({
			key: String(g.id),
			groupId: g.id,
			name: g.name,
			items: filteredMonitors.filter((m) => m.groupId === g.id)
		})),
		{
			key: 'ungrouped',
			groupId: null,
			name: 'Sans groupe',
			items: filteredMonitors.filter(
				(m) => m.groupId == null || !$groups.some((g) => g.id === m.groupId)
			)
		}
	].filter((sct) => sct.items.length > 0);

	// ── Tri & glisser-déposer ─────────────────────────────────────────────────
	const FLIP_MS = 160;
	let dragging = false;
	type Card = MonitorCardData;
	type Section = { key: string; id: number; groupId: number | null; name: string; items: Card[] };

	function statusRank(s: string): number {
		return s === 'down' ? 0 : s === 'checking' ? 1 : 2;
	}
	function sortCards(items: Card[], mode: SortMode, sectionKey: string): Card[] {
		if (mode === 'manual') return applyManualOrder(items, $monitorOrder[sectionKey] ?? []);
		const arr = [...items];
		if (mode === 'name') arr.sort((a, b) => a.name.localeCompare(b.name, 'fr'));
		else if (mode === 'status')
			arr.sort(
				(a, b) => statusRank(a.status) - statusRank(b.status) || a.name.localeCompare(b.name, 'fr')
			);
		else if (mode === 'latency') arr.sort((a, b) => (b.latency ?? -1) - (a.latency ?? -1));
		else if (mode === 'uptime') arr.sort((a, b) => (a.uptime24h ?? 101) - (b.uptime24h ?? 101));
		return arr;
	}
	function groupRank(items: Card[], mode: SortMode): number {
		if (!items.length) return mode === 'status' ? 2 : mode === 'uptime' ? 101 : 0;
		if (mode === 'status') return Math.min(...items.map((m) => statusRank(m.status)));
		if (mode === 'latency') return -Math.max(...items.map((m) => m.latency ?? -1));
		if (mode === 'uptime') return Math.min(...items.map((m) => m.uptime24h ?? 101));
		return 0;
	}

	// Vues mutables (re-synchronisées sauf pendant un glisser, pour ne pas casser le D&D)
	let flatCards: Card[] = [];
	let realSections: Section[] = [];
	let ungroupedSection: Section | null = null;

	$: if (!dragging) flatCards = sortCards(filteredMonitors, $sortMode, 'all');
	$: if (!dragging) {
		const real: Section[] = groupSections
			.filter((s) => s.groupId !== null)
			.map((s) => ({ ...s, id: s.groupId as number, items: sortCards(s.items, $sortMode, s.key) }));
		if ($sortMode === 'manual') {
			real.sort((a, b) => {
				const pa = $groupOrder.indexOf(a.id);
				const pb = $groupOrder.indexOf(b.id);
				return (pa === -1 ? 1e9 : pa) - (pb === -1 ? 1e9 : pb);
			});
		} else {
			real.sort(
				(a, b) =>
					groupRank(a.items, $sortMode) - groupRank(b.items, $sortMode) ||
					a.name.localeCompare(b.name, 'fr')
			);
		}
		realSections = real;
		const ung = groupSections.find((s) => s.groupId === null);
		ungroupedSection = ung
			? { ...ung, id: -1, items: sortCards(ung.items, $sortMode, ung.key) }
			: null;
	}

	$: dragDisabled = $sortMode !== 'manual';

	function persistCardOrder(key: string, items: Card[]) {
		monitorOrder.update((m) => ({ ...m, [key]: items.map((c) => c.id) }));
	}
	function setSectionItems(key: string, items: Card[]) {
		if (ungroupedSection && ungroupedSection.key === key)
			ungroupedSection = { ...ungroupedSection, items };
		else realSections = realSections.map((s) => (s.key === key ? { ...s, items } : s));
	}
	function flatConsider(e: CustomEvent) {
		dragging = true;
		flatCards = e.detail.items;
	}
	function flatFinalize(e: CustomEvent) {
		flatCards = e.detail.items;
		persistCardOrder('all', flatCards);
		dragging = false;
	}
	function sectionConsider(key: string, e: CustomEvent) {
		dragging = true;
		setSectionItems(key, e.detail.items);
	}
	function sectionFinalize(key: string, e: CustomEvent) {
		setSectionItems(key, e.detail.items);
		persistCardOrder(key, e.detail.items);
		dragging = false;
	}
	function groupsConsider(e: CustomEvent) {
		dragging = true;
		realSections = e.detail.items;
	}
	function groupsFinalize(e: CustomEvent) {
		realSections = e.detail.items;
		groupOrder.set(realSections.map((s) => s.id));
		dragging = false;
	}

	// Utilise la réactivité Svelte pour suivre le store auth
	$: authState = $auth;

	// Profil modal
	let showProfile = false;
	let profileConfirmDelete = false;
	let profileDeleting = false;
	let profileDeleteConfirmText = '';

	// Email change
	let profileNewEmail = '';
	let profileEmailSubmitting = false;
	let profileEmailError: string | null = null;
	let profileEmailSuccess: string | null = null;

	// Password change
	let profilePassword = '';
	let profileConfirmPassword = '';
	let profilePasswordValid = false;
	let profilePasswordSubmitting = false;
	let profilePasswordError: string | null = null;
	let profilePasswordSuccess: string | null = null;

	$: profilePasswordsMatch =
		profileConfirmPassword === '' || profilePassword === profileConfirmPassword;
	$: profileCanSavePassword =
		!profilePasswordSubmitting &&
		profilePassword !== '' &&
		profilePasswordValid &&
		profilePassword === profileConfirmPassword;

	// Webhook d'alerte de l'équipe (réutilisé par la section Équipe).
	let profileWebhookUrl = '';
	let profileWebhookKind = 'discord';
	let profileStatusPageSlug = '';
	let profileStatusPageTitle = '';
	let profileStatusPageSubmitting = false;
	let profileStatusPageError: string | null = null;
	let profileStatusPageSuccess: string | null = null;
	let profileApiTokens: {
		id: number;
		name: string;
		prefix: string;
		last_used_at: string | null;
	}[] = [];
	let profileNewTokenName = '';
	let profileNewTokenRaw = '';
	let profileTokenError: string | null = null;

	async function openProfile() {
		profileNewEmail = '';
		profileEmailError = null;
		profileEmailSuccess = null;
		profilePassword = '';
		profileConfirmPassword = '';
		profilePasswordError = null;
		profilePasswordSuccess = null;
		profileWebhookUrl = '';
		profileWebhookKind = 'discord';
		profileConfirmDelete = false;
		profileDeleteConfirmText = '';
		showProfile = true;
		profileStatusPageError = null;
		profileStatusPageSuccess = null;
		void loadStatusPage();
		profileNewTokenRaw = '';
		profileTokenError = null;
		void loadApiTokens();
	}

	async function loadApiTokens() {
		try {
			const res = await apiFetch('/api-tokens');
			if (res.ok) profileApiTokens = await res.json();
		} catch {
			/* best-effort */
		}
	}

	async function createApiToken() {
		if (!profileNewTokenName.trim()) return;
		profileTokenError = null;
		try {
			const res = await apiFetch('/api-tokens', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: profileNewTokenName.trim() })
			});
			if (!res.ok) {
				profileTokenError = await parseApiError(res, 'token API');
				return;
			}
			const created = await res.json();
			profileNewTokenRaw = created.token;
			profileNewTokenName = '';
			await loadApiTokens();
		} catch (e) {
			profileTokenError = parseNetworkError(e, 'token API');
		}
	}

	async function deleteApiToken(id: number) {
		profileTokenError = null;
		try {
			const res = await apiFetch(`/api-tokens/${id}`, { method: 'DELETE' });
			if (!res.ok && res.status !== 204) {
				profileTokenError = await parseApiError(res, 'token API');
				return;
			}
			await loadApiTokens();
		} catch (e) {
			profileTokenError = e instanceof Error ? e.message : 'Erreur inconnue';
		}
	}

	async function loadStatusPage() {
		try {
			const res = await apiFetch('/status-page');
			if (res.ok) {
				const sp = await res.json();
				if (sp) {
					profileStatusPageSlug = sp.slug ?? '';
					profileStatusPageTitle = sp.title ?? '';
				}
			}
		} catch {
			/* best-effort */
		}
	}

	async function saveStatusPage() {
		profileStatusPageSubmitting = true;
		profileStatusPageError = null;
		profileStatusPageSuccess = null;
		try {
			const res = await apiFetch('/status-page', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ slug: profileStatusPageSlug, title: profileStatusPageTitle })
			});
			if (!res.ok) {
				profileStatusPageError = await parseApiError(res, 'page publique');
			} else {
				profileStatusPageSuccess = 'Page publique enregistrée.';
			}
		} catch (e) {
			profileStatusPageError = parseNetworkError(e, 'page publique');
		} finally {
			profileStatusPageSubmitting = false;
		}
	}

	// ── Gestion d'équipe (membres, rôles, webhook, préférence email) ──────────
	type TeamMemberRow = {
		id: number;
		user_id: number;
		email: string;
		role: TeamRole;
		alert_email_enabled: boolean;
	};
	let teamMembers: TeamMemberRow[] = [];
	let teamMembersLoaded = false;
	let teamNameDraft = '';
	let teamSettingsError: string | null = null;
	let teamSettingsSuccess: string | null = null;
	let teamSettingsSubmitting = false;
	let inviteEmail = '';
	let inviteRole: TeamRole = 'member';
	let inviteError: string | null = null;
	let myEmailEnabled = true;
	let myEmailError: string | null = null;
	let newTeamName = '';
	let createTeamError: string | null = null;

	// Modal dédié « Espaces & équipes » (accès direct depuis le header).
	let showTeams = false;
	let teamsLoadedFor: number | null = null;
	function openTeams() {
		newTeamName = '';
		createTeamError = null;
		teamsLoadedFor = null; // force un rechargement à l'ouverture
		showTeams = true;
	}
	// Sélecteur d'espace du header : l'option spéciale « __add__ » ouvre le modal de
	// création au lieu de changer d'espace (on rétablit la sélection courante).
	function onTeamSelect(e: Event) {
		const sel = e.currentTarget as HTMLSelectElement;
		if (sel.value === '__add__') {
			sel.value = String($activeTeamId ?? '');
			openTeams();
			return;
		}
		activeTeamId.set(Number(sel.value));
	}
	// Recharge la gestion quand le modal est ouvert et que l'équipe gérée change.
	$: if (showTeams && $activeTeamId !== teamsLoadedFor) {
		teamsLoadedFor = $activeTeamId;
		void loadTeamManagement();
	}

	$: isTeamAdmin = $activeRole === 'admin';

	function roleLabel(r: string): string {
		return r === 'admin' ? 'Admin' : r === 'member' ? 'Membre' : 'Lecture seule';
	}

	async function loadTeamManagement() {
		teamMembers = [];
		teamMembersLoaded = false;
		teamSettingsError = null;
		teamSettingsSuccess = null;
		inviteError = null;
		myEmailError = null;
		const t = get(activeTeam);
		if (!t) {
			teamMembersLoaded = true;
			return;
		}
		teamNameDraft = t.name;
		profileWebhookUrl = t.alertWebhookUrl ?? '';
		profileWebhookKind = t.alertWebhookKind ?? 'discord';
		try {
			const res = await apiFetch(`/teams/${t.id}/members`);
			if (res.ok) {
				teamMembers = (await res.json()) as TeamMemberRow[];
				const me = teamMembers.find((m) => m.user_id === authState?.user?.id);
				if (me) myEmailEnabled = me.alert_email_enabled;
			}
		} catch {
			/* best-effort */
		} finally {
			teamMembersLoaded = true;
		}
	}

	async function saveTeamSettings() {
		const t = get(activeTeam);
		if (!t) return;
		teamSettingsSubmitting = true;
		teamSettingsError = null;
		teamSettingsSuccess = null;
		try {
			const res = await apiFetch(`/teams/${t.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: teamNameDraft.trim() || t.name,
					alert_webhook_url: profileWebhookUrl,
					alert_webhook_kind: profileWebhookKind
				})
			});
			if (!res.ok) {
				teamSettingsError = await parseApiError(res, 'équipe');
			} else {
				teamSettingsSuccess = 'Paramètres de l’équipe enregistrés.';
				await loadTeams();
			}
		} catch (e) {
			teamSettingsError = parseNetworkError(e, 'équipe');
		} finally {
			teamSettingsSubmitting = false;
		}
	}

	async function saveMyEmailPref() {
		const t = get(activeTeam);
		if (!t) return;
		myEmailError = null;
		try {
			const res = await apiFetch(`/teams/${t.id}/me`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ alert_email_enabled: myEmailEnabled })
			});
			if (!res.ok) myEmailError = await parseApiError(res, 'préférence');
		} catch (e) {
			myEmailError = parseNetworkError(e, 'préférence');
		}
	}

	async function inviteMember() {
		const t = get(activeTeam);
		if (!t || !inviteEmail.trim()) return;
		inviteError = null;
		try {
			const res = await apiFetch(`/teams/${t.id}/members`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole })
			});
			if (!res.ok) {
				inviteError = await parseApiError(res, 'invitation');
				return;
			}
			inviteEmail = '';
			inviteRole = 'member';
			await loadTeamManagement();
			await loadTeams();
		} catch (e) {
			inviteError = parseNetworkError(e, 'invitation');
		}
	}

	async function changeMemberRole(memberId: number, role: string) {
		const t = get(activeTeam);
		if (!t) return;
		inviteError = null;
		try {
			const res = await apiFetch(`/teams/${t.id}/members/${memberId}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ role })
			});
			if (!res.ok) inviteError = await parseApiError(res, 'rôle');
			await loadTeamManagement();
			await loadTeams();
		} catch (e) {
			inviteError = parseNetworkError(e, 'rôle');
		}
	}

	async function removeMember(memberId: number) {
		const t = get(activeTeam);
		if (!t) return;
		inviteError = null;
		try {
			const res = await apiFetch(`/teams/${t.id}/members/${memberId}`, { method: 'DELETE' });
			if (!res.ok && res.status !== 204) {
				inviteError = await parseApiError(res, 'membre');
				return;
			}
			await loadTeamManagement();
			await loadTeams();
		} catch (e) {
			inviteError = parseNetworkError(e, 'membre');
		}
	}

	async function createTeam() {
		const name = newTeamName.trim();
		if (!name) return;
		createTeamError = null;
		try {
			const res = await apiFetch('/teams', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name })
			});
			if (!res.ok) {
				createTeamError = await parseApiError(res, 'équipe');
				return;
			}
			const created = await res.json();
			newTeamName = '';
			await loadTeams();
			activeTeamId.set(created.id);
			await loadTeamManagement();
		} catch (e) {
			createTeamError = parseNetworkError(e, 'équipe');
		}
	}

	// Suppression différée de l'espace (désactivation puis purge après 7 j), réactivable.
	const TEAM_DELETION_GRACE_DAYS = 7;
	let confirmDeleteTeam = false;
	let deleteTeamConfirmText = '';
	let deleteTeamError: string | null = null;
	let deleteTeamSubmitting = false;

	$: activeTeamScheduled = $activeTeam?.deletionScheduledAt ?? null;
	$: activeTeamCount = $teams.filter((t) => !t.deletionScheduledAt).length;
	// On peut supprimer si admin, espace pas déjà planifié, et il reste un AUTRE espace actif.
	$: canDeleteActiveTeam = isTeamAdmin && !activeTeamScheduled && activeTeamCount > 1;

	function teamPurgeDate(scheduledAt: string): string {
		const d = new Date(new Date(scheduledAt).getTime() + TEAM_DELETION_GRACE_DAYS * 86400000);
		return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
	}

	function openDeleteTeam() {
		deleteTeamConfirmText = '';
		deleteTeamError = null;
		confirmDeleteTeam = true;
	}

	async function scheduleDeleteTeam() {
		const t = get(activeTeam);
		if (!t) return;
		deleteTeamSubmitting = true;
		deleteTeamError = null;
		try {
			const res = await apiFetch(`/teams/${t.id}`, { method: 'DELETE' });
			if (!res.ok) {
				deleteTeamError = await parseApiError(res, 'suppression');
				return;
			}
			confirmDeleteTeam = false;
			await loadTeams();
			// Bascule sur un espace encore actif si le courant vient d'être désactivé.
			const stillActive = get(teams).filter((x) => !x.deletionScheduledAt);
			if (stillActive.length && !stillActive.some((x) => x.id === get(activeTeamId))) {
				activeTeamId.set(stillActive[0].id);
			}
			await loadTeamManagement();
		} catch (e) {
			deleteTeamError = parseNetworkError(e, 'suppression');
		} finally {
			deleteTeamSubmitting = false;
		}
	}

	async function restoreActiveTeam() {
		const t = get(activeTeam);
		if (!t) return;
		try {
			const res = await apiFetch(`/teams/${t.id}/restore`, { method: 'POST' });
			if (res.ok) {
				await loadTeams();
				await loadTeamManagement();
			}
		} catch {
			/* best-effort */
		}
	}

	async function submitEmailChange() {
		profileEmailSubmitting = true;
		profileEmailError = null;
		profileEmailSuccess = null;
		try {
			const res = await apiFetch('/auth/change-email', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ new_email: profileNewEmail })
			});
			if (!res.ok) {
				profileEmailError = await parseApiError(res, 'changement email');
			} else {
				const data = await res.json();
				profileEmailSuccess = data.message;
				profileNewEmail = '';
			}
		} catch (e) {
			profileEmailError = parseNetworkError(e, 'changement email');
		} finally {
			profileEmailSubmitting = false;
		}
	}

	async function deleteAccount() {
		profileDeleting = true;
		try {
			const res = await apiFetch('/auth/me', { method: 'DELETE' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			clearAuth();
			goto('/login');
		} catch (e) {
			profilePasswordError = e instanceof Error ? e.message : 'Erreur inconnue';
			profileDeleting = false;
			profileConfirmDelete = false;
		}
	}

	async function savePassword() {
		profilePasswordSubmitting = true;
		profilePasswordError = null;
		profilePasswordSuccess = null;
		try {
			const res = await apiFetch('/auth/me', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ password: profilePassword })
			});

			if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));

			profilePasswordSuccess = 'Mot de passe mis à jour.';
			profilePassword = '';
			profileConfirmPassword = '';
		} catch (e) {
			profilePasswordError = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			profilePasswordSubmitting = false;
		}
	}

	function logout() {
		clearAuth();
		goto('/login');
	}

	async function fetchHistory(monitorId: number, signal?: AbortSignal): Promise<CheckEntry[]> {
		try {
			const res = await apiFetch(`/monitors/${monitorId}/history`, { signal });
			if (!res.ok) return [];
			return (await res.json()) as CheckEntry[];
		} catch {
			return [];
		}
	}

	// Annule un rafraîchissement en cours si un nouveau démarre (évite les courses).
	let monitorsAbort: AbortController | null = null;

	async function fetchMonitors() {
		monitorsAbort?.abort();
		const controller = new AbortController();
		monitorsAbort = controller;
		const { signal } = controller;

		loading = true;
		error = null;
		const minDelay = new Promise((r) => setTimeout(r, 1000));
		try {
			if (!authState?.token) {
				await goto('/login');
				return;
			}

			const tid = get(activeTeamId);
			if (tid == null) {
				monitors.set([]);
				return;
			}
			const res = await apiFetch(`/monitors?team_id=${tid}`, { signal });

			if (!res.ok) {
				throw new Error(await parseApiError(res, 'chargement des monitors'));
			}

			const data = (await res.json()) as MonitorFromApi[];

			// Récupère l'historique de chaque monitor en parallèle
			const histories = await Promise.all(data.map((m) => fetchHistory(m.id, signal)));
			if (signal.aborted) return;

			monitors.set(
				data.map((m, i) => ({
					id: m.id,
					name: m.name,
					url: m.url,
					status: m.status === 'unknown' ? 'checking' : (m.status as 'up' | 'down'),
					type: m.type,
					latency: m.last_latency_ms,
					history: histories[i],
					lastCheckedAt: m.last_checked_at,
					expectedStatusCode: m.expected_status_code,
					lastStatusCode: m.last_status_code,
					sslExpiryAt: m.ssl_expiry_at,
					uptime24h: m.uptime_24h,
					uptime7d: m.uptime_7d,
					uptime30d: m.uptime_30d,
					uptime90d: m.uptime_90d,
					checkIntervalSeconds: m.check_interval_seconds,
					keyword: m.keyword,
					keywordMode: m.keyword_mode ?? 'present',
					latencyThresholdMs: m.latency_threshold_ms,
					port: m.port,
					groupId: m.group_id,
					teamId: m.team_id,
					environment: m.environment,
					isPublic: m.is_public,
					inMaintenance: m.in_maintenance,
					createdAt: m.created_at
				}))
			);
		} catch (err) {
			if ((err as Error)?.name === 'AbortError') return;
			error = parseNetworkError(err, 'chargement des monitors');
		} finally {
			await minDelay;
			// Ne touche loading que si ce rafraîchissement est toujours le plus récent.
			if (monitorsAbort === controller) loading = false;
		}
	}

	async function checkAdmin() {
		if (!authState?.token) return;
		try {
			const res = await apiFetch('/admin/check');
			if (res.ok) {
				const data = await res.json();
				isAdmin = data.is_admin;
			}
		} catch {
			/* ignore — admin check is best-effort */
		}
	}

	// Recharge monitors + groupes quand l'équipe active change (après le 1er chargement).
	let teamsReady = false;
	let lastTeamLoaded: number | null | undefined = undefined;
	async function reloadForActiveTeam() {
		await Promise.all([fetchMonitors(), loadGroups(get(activeTeamId))]);
	}
	$: if (teamsReady && $activeTeamId !== lastTeamLoaded) {
		lastTeamLoaded = $activeTeamId;
		reloadForActiveTeam();
	}

	onMount(async () => {
		if (!authState?.token) {
			await goto('/login');
			return;
		}
		await loadTeams();
		teamsReady = true; // déclenche reloadForActiveTeam via le bloc réactif ci-dessus
		checkAdmin();
		preloadCode('/profile', '/add', '/login');
	});
</script>

<!-- Caché tant qu'on n'est pas authentifié : onMount redirige vers /login (anti-flash). -->
<div
	class="min-h-screen flex items-start justify-center pt-10 pb-12"
	class:hidden={!authState?.token}
>
	<div
		class="w-full max-w-6xl mx-auto
           rounded-3xl bg-white/80 dark:bg-slate-900/90 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg
           overflow-hidden"
	>
		<div class="border-b border-slate-200/60 dark:border-slate-800/80">
			<div class="flex items-center justify-between gap-4 px-8 pt-7 pb-4">
				<!-- Left: branding + title -->
				<div class="flex flex-col gap-0.5">
					<div class="eyebrow">GotYeah Monitor</div>
					<div class="text-2xl font-bold text-slate-900 dark:text-slate-50 tracking-tight">
						Moniteurs
					</div>
				</div>

				<!-- Right: actions -->
				<div class="flex items-center gap-2">
					<!-- Sélecteur d'équipe + rôle -->
					{#if $teams.length > 0}
						<select
							value={$activeTeamId}
							on:change={onTeamSelect}
							class="field w-auto shrink-0 text-sm max-w-[160px]"
							title="Espace actif"
							aria-label="Espace actif"
						>
							{#each $teams as t (t.id)}
								<option value={t.id}>{t.name}</option>
							{/each}
							<option value="__add__">+ Ajouter un espace…</option>
						</select>
					{/if}
					{#if isReadonly}
						<span
							class="px-2 py-1 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 whitespace-nowrap"
							title="Vous êtes en lecture seule dans cette équipe">lecture seule</span
						>
					{/if}

					<!-- Gérer les équipes / créer un espace -->
					<button
						type="button"
						class="h-8 flex items-center gap-1.5 px-3 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:text-cyan-500 dark:hover:text-cyan-400 hover:border-cyan-300 dark:hover:border-cyan-700 transition-all text-sm font-semibold"
						on:click={openTeams}
						title="Gérer les équipes et créer un espace"
					>
						<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
							<path
								d="M13 7a3 3 0 11-6 0 3 3 0 016 0zM7.5 11a4.5 4.5 0 00-4.473 4.001A1 1 0 004 16h8a1 1 0 00.973-1.001A4.5 4.5 0 008.5 11h-1zM16 7a2 2 0 11-4 0 2 2 0 014 0zM15.001 10a3.5 3.5 0 013.473 3.04A1 1 0 0117.5 14h-2.6a5.49 5.49 0 00-.78-2.93c.27-.046.547-.07.83-.07h.05z"
							/>
						</svg>
						Équipes
					</button>

					<!-- View toggle -->
					<div
						class="flex items-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 p-0.5 gap-0.5 cursor-pointer"
						on:click={() => (viewMode = viewMode === 'grid' ? 'list' : 'grid')}
						role="button"
						tabindex="0"
						on:keydown={(e) =>
							e.key === 'Enter' && (viewMode = viewMode === 'grid' ? 'list' : 'grid')}
					>
						<span
							class="rounded-full p-1.5 transition-all {viewMode === 'grid'
								? 'bg-white dark:bg-slate-700 shadow-sm text-cyan-500'
								: 'text-slate-400'}"
						>
							<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
								<rect x="1" y="1" width="6" height="6" rx="1" /><rect
									x="9"
									y="1"
									width="6"
									height="6"
									rx="1"
								/><rect x="1" y="9" width="6" height="6" rx="1" /><rect
									x="9"
									y="9"
									width="6"
									height="6"
									rx="1"
								/>
							</svg>
						</span>
						<span
							class="rounded-full p-1.5 transition-all {viewMode === 'list'
								? 'bg-white dark:bg-slate-700 shadow-sm text-cyan-500'
								: 'text-slate-400'}"
						>
							<svg
								class="w-3.5 h-3.5"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 16 16"
							>
								<line x1="3" y1="4" x2="13" y2="4" /><line x1="3" y1="8" x2="13" y2="8" /><line
									x1="3"
									y1="12"
									x2="13"
									y2="12"
								/>
							</svg>
						</span>
					</div>

					<!-- Refresh -->
					<button
						type="button"
						class="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 hover:text-cyan-500 dark:hover:text-cyan-400 hover:border-cyan-300 dark:hover:border-cyan-700 transition-all disabled:opacity-40"
						on:click={fetchMonitors}
						disabled={loading}
						title="Rafraîchir"
					>
						<svg
							class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
							/>
						</svg>
					</button>

					<!-- Separator -->
					<div class="h-5 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

					<!-- Admin badge -->
					{#if isAdmin}
						<button
							type="button"
							class="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold
							   bg-amber-500 hover:bg-amber-600 text-white
							   shadow-sm
							   transition-all"
							on:click={() => goto('/admin')}
						>
							<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
								<path
									fill-rule="evenodd"
									d="M18 8a6 6 0 01-7.743 5.743L10 14l-1 1-1 1H6v2H2v-4l4.257-4.257A6 6 0 1118 8zm-6-4a1 1 0 100 2 2 2 0 012 2 1 1 0 102 0 4 4 0 00-4-4z"
									clip-rule="evenodd"
								/>
							</svg>
							Admin
						</button>
					{/if}

					<!-- Add button -->
					{#if canEdit}
						<button
							type="button"
							class="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold
						   bg-cyan-500 hover:bg-cyan-600 text-white
						   shadow-sm
						   transition-all"
							on:click={() => openAdd()}
						>
							<svg
								class="w-3.5 h-3.5"
								fill="none"
								stroke="currentColor"
								stroke-width="3"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
							</svg>
							Ajouter
						</button>
					{/if}

					<!-- Separator -->
					<div class="h-5 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

					<!-- Profile -->
					<button
						type="button"
						class="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-800/70 hover:border-cyan-300 dark:hover:border-cyan-700 transition-all"
						on:click={openProfile}
					>
						<span
							class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-cyan-600 text-white text-xs font-bold shadow"
						>
							{authState?.user?.email?.[0]?.toUpperCase() ?? '?'}
						</span>
						<span class="text-xs text-slate-600 dark:text-slate-300 max-w-[120px] truncate">
							{authState?.user?.email ?? 'Profil'}
						</span>
					</button>

					<!-- Logout -->
					<button
						type="button"
						class="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 text-slate-400 hover:text-rose-500 hover:border-rose-300 dark:hover:border-rose-700 transition-all"
						on:click={logout}
						title="Déconnexion"
					>
						<svg
							class="w-3.5 h-3.5"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
							/>
						</svg>
					</button>
				</div>
			</div>
			{#if loading || $monitors.length > 0}
				<div class="flex items-center gap-2 px-8 pb-5">
					<input
						type="search"
						bind:value={search}
						placeholder="Rechercher un moniteur…"
						class="field flex-1"
					/>
					<select
						bind:value={$sortMode}
						class="field w-auto shrink-0"
						title="Trier les moniteurs"
						aria-label="Trier les moniteurs"
					>
						{#each SORT_OPTIONS as opt (opt.value)}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
					{#if envOptions.length > 0}
						<select
							bind:value={envFilter}
							class="field w-auto shrink-0"
							title="Filtrer par environnement"
							aria-label="Filtrer par environnement"
						>
							<option value="">Tous les environnements</option>
							{#each envOptions as env (env)}
								<option value={env}>{env}</option>
							{/each}
						</select>
					{/if}
					{#if canEdit}
						<button
							type="button"
							class="btn btn-sm btn-secondary whitespace-nowrap"
							on:click={() => (showGroups = true)}
						>
							Gérer les groupes
						</button>
					{/if}
				</div>
			{/if}
		</div>

		{#if error}
			<div
				class="mx-8 mt-4 flex items-start gap-2 text-sm text-rose-600 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-xl px-4 py-3"
			>
				<svg
					class="w-4 h-4 shrink-0 mt-0.5"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
					/>
				</svg>
				{error}
			</div>
		{/if}

		{#if !loading && $monitors.length === 0}
			<div class="flex flex-col items-center justify-center gap-5 py-20 px-8 text-center">
				<div
					class="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-100 dark:border-cyan-800"
				>
					<svg
						class="w-8 h-8 text-cyan-400"
						fill="none"
						stroke="currentColor"
						stroke-width="1.5"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0H3"
						/>
					</svg>
				</div>
				<div class="flex flex-col gap-1">
					<p class="text-base font-semibold text-slate-800 dark:text-slate-100">
						Aucun moniteur pour l'instant
					</p>
					<p class="text-sm text-slate-400 dark:text-slate-500 max-w-xs">
						Ajoutez votre premier site ou service à surveiller pour commencer.
					</p>
				</div>
				{#if canEdit}
					<button
						type="button"
						class="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold
						   bg-cyan-500 hover:bg-cyan-600 text-white
						   shadow-sm
						   transition-all"
						on:click={() => openAdd()}
					>
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							stroke-width="3"
							viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
						</svg>
						Ajouter un moniteur
					</button>
				{/if}
			</div>
		{:else if $groups.length === 0}
			<div
				class={(viewMode === 'grid'
					? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-start'
					: 'flex flex-col gap-4') + ' p-8'}
				use:dndzone={{ items: flatCards, dragDisabled, flipDurationMs: FLIP_MS, type: 'cards' }}
				on:consider={flatConsider}
				on:finalize={flatFinalize}
			>
				{#each flatCards as m (m.id)}
					<MonitorCard
						{...m}
						showDetails={openCardId === m.id}
						onToggleDetails={() => toggleCardDetails(m.id)}
						onDeleted={fetchMonitors}
						groups={$groups}
						onAssignGroup={assignGroup}
						compact={viewMode === 'list'}
					/>
				{/each}
			</div>
		{:else}
			<div class="flex flex-col gap-2 p-8">
				<div
					class="flex flex-col gap-2"
					use:dndzone={{
						items: realSections,
						dragDisabled,
						flipDurationMs: FLIP_MS,
						type: 'groups'
					}}
					on:consider={groupsConsider}
					on:finalize={groupsFinalize}
				>
					{#each realSections as section (section.id)}
						<div>
							<div class="flex items-center gap-1">
								{#if $sortMode === 'manual' && section.groupId !== null}
									<span
										class="cursor-grab text-slate-400 hover:text-slate-500 shrink-0 select-none"
										aria-hidden="true"
										title="Glisser pour réordonner le groupe"
									>
										<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
											<circle cx="7" cy="5" r="1.5" /><circle cx="13" cy="5" r="1.5" /><circle
												cx="7"
												cy="10"
												r="1.5"
											/><circle cx="13" cy="10" r="1.5" /><circle cx="7" cy="15" r="1.5" /><circle
												cx="13"
												cy="15"
												r="1.5"
											/>
										</svg>
									</span>
								{/if}
								<button
									type="button"
									class="flex items-center gap-2 flex-1 text-left py-2 text-sm font-semibold text-slate-700 dark:text-slate-200"
									on:click={() => toggleGroupCollapse(section.key)}
								>
									<span class="text-slate-400">{$groupCollapse[section.key] ? '▸' : '▾'}</span>
									{section.name}
									<span class="text-xs font-normal text-slate-400">({section.items.length})</span>
									{#if $groupCollapse[section.key]}
										<span class="flex items-center gap-1 ml-1 flex-wrap">
											{#each section.items as m (m.id)}
												<span
													class="h-2 w-2 rounded-full shrink-0 {m.status === 'up'
														? 'bg-emerald-400'
														: m.status === 'down'
															? 'bg-rose-400'
															: 'bg-sky-300'}"
												></span>
											{/each}
										</span>
									{/if}
								</button>
								{#if section.groupId !== null && canEdit}
									<button
										type="button"
										class="h-6 w-6 flex items-center justify-center rounded-full text-slate-400 hover:text-cyan-500 hover:bg-cyan-500/10 transition-colors shrink-0"
										title={`Ajouter un moniteur dans « ${section.name} »`}
										on:click={() => openAdd(section.groupId)}
									>
										<svg
											class="w-3.5 h-3.5"
											fill="none"
											stroke="currentColor"
											stroke-width="2.5"
											viewBox="0 0 24 24"
										>
											<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
										</svg>
									</button>
								{/if}
							</div>
							{#if !$groupCollapse[section.key]}
								<div
									class={(viewMode === 'grid'
										? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-start'
										: 'flex flex-col gap-4') + ' pb-4'}
									use:dndzone={{
										items: section.items,
										dragDisabled,
										flipDurationMs: FLIP_MS,
										type: 'cards'
									}}
									on:consider={(e) => sectionConsider(section.key, e)}
									on:finalize={(e) => sectionFinalize(section.key, e)}
								>
									{#each section.items as m (m.id)}
										<MonitorCard
											{...m}
											showDetails={openCardId === m.id}
											onToggleDetails={() => toggleCardDetails(m.id)}
											onDeleted={fetchMonitors}
											groups={$groups}
											onAssignGroup={assignGroup}
											compact={viewMode === 'list'}
										/>
									{/each}
								</div>
							{/if}
						</div>
					{/each}
				</div>
				{#if ungroupedSection}
					{@const section = ungroupedSection}
					<div>
						<div class="flex items-center gap-1">
							{#if $sortMode === 'manual' && section.groupId !== null}
								<span
									class="cursor-grab text-slate-400 hover:text-slate-500 shrink-0 select-none"
									aria-hidden="true"
									title="Glisser pour réordonner le groupe"
								>
									<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
										<circle cx="7" cy="5" r="1.5" /><circle cx="13" cy="5" r="1.5" /><circle
											cx="7"
											cy="10"
											r="1.5"
										/><circle cx="13" cy="10" r="1.5" /><circle cx="7" cy="15" r="1.5" /><circle
											cx="13"
											cy="15"
											r="1.5"
										/>
									</svg>
								</span>
							{/if}
							<button
								type="button"
								class="flex items-center gap-2 flex-1 text-left py-2 text-sm font-semibold text-slate-700 dark:text-slate-200"
								on:click={() => toggleGroupCollapse(section.key)}
							>
								<span class="text-slate-400">{$groupCollapse[section.key] ? '▸' : '▾'}</span>
								{section.name}
								<span class="text-xs font-normal text-slate-400">({section.items.length})</span>
								{#if $groupCollapse[section.key]}
									<span class="flex items-center gap-1 ml-1 flex-wrap">
										{#each section.items as m (m.id)}
											<span
												class="h-2 w-2 rounded-full shrink-0 {m.status === 'up'
													? 'bg-emerald-400'
													: m.status === 'down'
														? 'bg-rose-400'
														: 'bg-sky-300'}"
											></span>
										{/each}
									</span>
								{/if}
							</button>
							{#if section.groupId !== null}
								<button
									type="button"
									class="h-6 w-6 flex items-center justify-center rounded-full text-slate-400 hover:text-cyan-500 hover:bg-cyan-500/10 transition-colors shrink-0"
									title={`Ajouter un moniteur dans « ${section.name} »`}
									on:click={() => openAdd(section.groupId)}
								>
									<svg
										class="w-3.5 h-3.5"
										fill="none"
										stroke="currentColor"
										stroke-width="2.5"
										viewBox="0 0 24 24"
									>
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
									</svg>
								</button>
							{/if}
						</div>
						{#if !$groupCollapse[section.key]}
							<div
								class={(viewMode === 'grid'
									? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-start'
									: 'flex flex-col gap-4') + ' pb-4'}
								use:dndzone={{
									items: section.items,
									dragDisabled,
									flipDurationMs: FLIP_MS,
									type: 'cards'
								}}
								on:consider={(e) => sectionConsider(section.key, e)}
								on:finalize={(e) => sectionFinalize(section.key, e)}
							>
								{#each section.items as m (m.id)}
									<MonitorCard
										{...m}
										showDetails={openCardId === m.id}
										onToggleDetails={() => toggleCardDetails(m.id)}
										onDeleted={fetchMonitors}
										groups={$groups}
										onAssignGroup={assignGroup}
										compact={viewMode === 'list'}
									/>
								{/each}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#if openCardId !== null}
	{@const selectedMonitor = $monitors.find((m) => m.id === openCardId)}
	{#if selectedMonitor}
		<MonitorDetailModal
			monitor={selectedMonitor}
			onClose={() => (openCardId = null)}
			onDeleted={fetchMonitors}
		/>
	{/if}
{/if}

{#if showAdd}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40"
		on:click={() => (showAdd = false)}
		role="presentation"
		use:modal={() => (showAdd = false)}
	>
		<div
			class="w-full max-w-sm mx-4 rounded-2xl bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-soft-lg p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="flex items-center justify-between">
				<h2 class="font-semibold text-slate-900 dark:text-slate-50">Ajouter un monitor</h2>
				<button
					type="button"
					class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
					on:click={() => (showAdd = false)}
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<form class="flex flex-col gap-3" on:submit|preventDefault={submitAdd}>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">Nom</span>
					<input class="field" bind:value={addName} placeholder="Ex: Backend API" required />
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">URL</span>
					<input
						class="field"
						bind:value={addUrl}
						placeholder="https://example.com/health"
						required
					/>
				</label>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Type</span>
						<select class="field" bind:value={addType}>
							<option value="http">HTTP</option>
							<option value="ping">Ping</option>
							<option value="port">Port</option>
						</select>
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Code HTTP attendu</span>
						<input
							type="number"
							min="100"
							max="599"
							class="field"
							bind:value={addExpectedStatusCode}
						/>
					</label>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Intervalle (s)</span>
						<input
							type="number"
							min="60"
							max="86400"
							class="field"
							bind:value={addCheckIntervalSeconds}
							placeholder="600 (défaut)"
						/>
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Seuil latence (ms)</span>
						<input
							type="number"
							min="1"
							class="field"
							bind:value={addLatencyThresholdMs}
							placeholder="désactivé"
						/>
					</label>
				</div>

				<label class="flex items-center gap-2 cursor-pointer">
					<input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={addIsPublic} />
					<span class="text-xs text-slate-600 dark:text-slate-300"
						>Afficher sur la page de statut publique</span
					>
				</label>
				{#if $groups.length > 0}
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Groupe</span>
						<select bind:value={addGroupId} class="field">
							<option value={null}>Sans groupe</option>
							{#each $groups as g (g.id)}
								<option value={g.id}>{g.name}</option>
							{/each}
						</select>
					</label>
				{/if}
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">Environnement</span>
					<input
						class="field"
						list="env-presets-add"
						bind:value={addEnvironment}
						placeholder="prod, staging, dev… (optionnel)"
					/>
					<datalist id="env-presets-add">
						<option value="prod"></option>
						<option value="staging"></option>
						<option value="dev"></option>
					</datalist>
				</label>
				{#if addType === 'http'}
					<div class="grid grid-cols-2 gap-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400">Mot-clé</span>
							<input
								class="field"
								bind:value={addKeyword}
								placeholder="texte attendu (optionnel)"
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400">Mode</span>
							<select class="field" bind:value={addKeywordMode}>
								<option value="present">doit être présent</option>
								<option value="absent">doit être absent</option>
							</select>
						</label>
					</div>
				{/if}

				{#if addType === 'port'}
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Port</span>
						<input
							type="number"
							min="1"
							max="65535"
							class="field"
							bind:value={addPort}
							placeholder="ex: 5432"
							required
						/>
					</label>
				{/if}

				{#if addError}
					<p
						class="text-xs text-rose-500 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
					>
						{addError}
					</p>
				{/if}

				<div class="flex gap-2 justify-end pt-1">
					<button type="button" class="btn btn-sm btn-secondary" on:click={() => (showAdd = false)}>
						Annuler
					</button>
					<button
						type="submit"
						class="btn btn-sm btn-primary disabled:opacity-50"
						disabled={addSubmitting}
					>
						{addSubmitting ? 'Ajout...' : 'Ajouter'}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

{#if showGroups}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40 px-4"
		on:click={() => (showGroups = false)}
		role="presentation"
		use:modal={() => (showGroups = false)}
	>
		<div
			class="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-soft-lg p-6 flex flex-col gap-4 max-h-[90vh] overflow-y-auto"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="flex items-center justify-between">
				<h2 class="font-semibold text-slate-900 dark:text-slate-50">Groupes</h2>
				<button
					type="button"
					class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
					on:click={() => (showGroups = false)}>✕</button
				>
			</div>
			<div class="flex flex-col gap-2 max-h-[50vh] overflow-y-auto">
				{#each $groups as g (g.id)}
					<div
						class="flex flex-col gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 p-2"
					>
						<div class="flex items-center gap-2">
							<input
								class="flex-1 field"
								value={g.name}
								on:change={(e) => renameGroup(g.id, e.currentTarget.value)}
							/>
							<button
								type="button"
								class="btn btn-sm btn-secondary"
								on:click={() => deleteGroup(g.id)}>Suppr.</button
							>
						</div>
						{#each $monitors.filter((m) => m.groupId === g.id) as mem (mem.id)}
							<div class="flex items-center gap-2 pl-1 text-xs">
								<span class="text-slate-600 dark:text-slate-300">{mem.name}</span>
								<button
									type="button"
									class="ml-auto text-rose-400 hover:text-rose-300"
									on:click={() => assignGroup(mem.id, null)}>retirer</button
								>
							</div>
						{/each}
						<select
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-2 py-1.5 text-xs text-slate-600 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-cyan-500"
							on:change={(e) => {
								const v = e.currentTarget.value;
								e.currentTarget.value = '';
								if (v) assignGroup(Number(v), g.id);
							}}
						>
							<option value="">+ Ajouter un moniteur…</option>
							{#each $monitors.filter((m) => m.groupId !== g.id) as opt (opt.id)}
								<option value={String(opt.id)}>{opt.name}</option>
							{/each}
						</select>
						<button
							type="button"
							class="self-start text-[11px] text-cyan-600 hover:underline"
							on:click={() => (groupRecipientsOpen = groupRecipientsOpen === g.id ? null : g.id)}
						>
							{groupRecipientsOpen === g.id ? '▾' : '▸'} Destinataires d'alerte du groupe
						</button>
						{#if groupRecipientsOpen === g.id}
							<div class="rounded-lg bg-slate-50 dark:bg-slate-800/60 p-2">
								<p class="text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
									Notifiés pour tous les moniteurs de ce groupe (en plus des destinataires propres à
									chaque moniteur).
								</p>
								<RecipientsEditor
									basePath={`/groups/${g.id}`}
									teamId={$activeTeamId}
									dark={false}
								/>
							</div>
						{/if}
					</div>
				{/each}
				{#if $groups.length === 0}
					<p class="text-sm text-slate-400">Aucun groupe pour l'instant.</p>
				{/if}
			</div>
			<form class="flex items-center gap-2" on:submit|preventDefault={createGroup}>
				<input class="flex-1 field" bind:value={newGroupName} placeholder="Nouveau groupe" />
				<button type="submit" class="btn btn-sm btn-primary">Créer</button>
			</form>
			{#if groupActionError}
				<p class="text-xs text-rose-500">{groupActionError}</p>
			{/if}
		</div>
	</div>
{/if}

{#if showProfile}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40 px-4"
		on:click={() => (showProfile = false)}
		role="presentation"
		use:modal={() => (showProfile = false)}
	>
		<div
			class="w-full max-w-lg rounded-2xl overflow-hidden
                   bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-soft-lg"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<!-- Body -->
			<div class="px-5 pb-5 pt-5 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">
				<div class="flex items-center justify-between mb-1">
					<h2 class="text-sm font-semibold text-slate-800 dark:text-slate-100">Mon profil</h2>
					<button
						type="button"
						class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
						on:click={() => (showProfile = false)}
					>
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				<!-- Changer l'adresse email -->
				<form
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
					on:submit|preventDefault={submitEmailChange}
				>
					<p class="eyebrow">Adresse email</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Email actuel</span>
						<input
							type="email"
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900/60 px-3 py-2 text-sm text-slate-500 dark:text-slate-400 cursor-not-allowed"
							value={authState?.user?.email ?? ''}
							disabled
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Nouvelle adresse email</span>
						<input
							type="email"
							class="field"
							bind:value={profileNewEmail}
							placeholder="nouvelle@adresse.com"
							required
						/>
					</label>

					{#if profileEmailError}
						<div
							class="flex items-start gap-2 text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0 mt-0.5"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
								/>
							</svg>
							{profileEmailError}
						</div>
					{/if}
					{#if profileEmailSuccess}
						<div
							class="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
							</svg>
							{profileEmailSuccess}
						</div>
					{/if}

					<div class="flex justify-end pt-1">
						<button
							type="submit"
							class="btn btn-sm btn-primary disabled:opacity-50"
							disabled={profileEmailSubmitting || !profileNewEmail}
						>
							{profileEmailSubmitting ? 'Envoi...' : 'Envoyer le lien de confirmation'}
						</button>
					</div>
				</form>

				<!-- Page publique -->
				<form
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
					on:submit|preventDefault={saveStatusPage}
				>
					<p class="eyebrow">Page publique</p>
					<p class="text-xs text-slate-500 dark:text-slate-400 -mt-1">
						Publie une page de statut accessible sans connexion, listant les moniteurs marqués «
						publics ».
					</p>
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Identifiant d'URL (slug)</span>
						<input class="field" bind:value={profileStatusPageSlug} placeholder="mon-statut" />
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Titre</span>
						<input
							class="field"
							bind:value={profileStatusPageTitle}
							placeholder="Statut de mes services"
						/>
					</label>
					{#if profileStatusPageSlug}
						<a
							href={`/status/${profileStatusPageSlug}`}
							target="_blank"
							rel="noreferrer"
							class="text-xs text-cyan-600 hover:underline"
							>Voir la page → /status/{profileStatusPageSlug}</a
						>
					{/if}
					{#if profileStatusPageError}<div
							class="text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
						>
							{profileStatusPageError}
						</div>{/if}
					{#if profileStatusPageSuccess}<div
							class="text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
						>
							{profileStatusPageSuccess}
						</div>{/if}
					<div class="flex justify-end pt-1">
						<button
							type="submit"
							class="btn btn-sm btn-primary disabled:opacity-50"
							disabled={profileStatusPageSubmitting}
							>{profileStatusPageSubmitting ? 'Enregistrement...' : 'Enregistrer'}</button
						>
					</div>
				</form>

				<!-- Tokens d'API -->
				<div
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
				>
					<p class="eyebrow">Tokens d'API (lecture)</p>
					<p class="text-xs text-slate-500 dark:text-slate-400 -mt-1">
						Pour interroger l'API en lecture (Grafana, scripts) sans mot de passe. En-tête : <code
							>Authorization: Bearer gym_…</code
						>
					</p>
					{#if profileNewTokenRaw}
						<div
							class="text-xs bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 flex flex-col gap-1"
						>
							<span class="text-amber-700 dark:text-amber-300"
								>Copie ce token maintenant — il ne sera plus affiché :</span
							>
							<code class="break-all text-slate-800 dark:text-slate-100">{profileNewTokenRaw}</code>
						</div>
					{/if}
					{#each profileApiTokens as t (t.id)}
						<div class="flex items-center gap-2 text-xs">
							<span class="font-medium text-slate-700 dark:text-slate-200">{t.name}</span>
							<code class="text-slate-400">{t.prefix}…</code>
							<span class="text-slate-400">{t.last_used_at ? 'utilisé' : 'jamais utilisé'}</span>
							<button
								type="button"
								class="ml-auto text-rose-500 hover:text-rose-400"
								on:click={() => deleteApiToken(t.id)}>Révoquer</button
							>
						</div>
					{/each}
					{#if profileTokenError}<p class="text-xs text-rose-500">{profileTokenError}</p>{/if}
					<div class="flex items-center gap-2">
						<input
							class="flex-1 field"
							bind:value={profileNewTokenName}
							placeholder="Nom du token"
						/>
						<button type="button" class="btn btn-sm btn-primary" on:click={createApiToken}
							>Créer</button
						>
					</div>
				</div>

				<!-- Changer le mot de passe -->
				<form
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
					on:submit|preventDefault={savePassword}
				>
					<p class="eyebrow">Mot de passe</p>

					<div class="flex flex-col gap-1">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400">Nouveau mot de passe</span>
							<input
								type="password"
								class="field"
								bind:value={profilePassword}
								placeholder="Nouveau mot de passe"
							/>
						</label>
						<PasswordStrength password={profilePassword} bind:valid={profilePasswordValid} />
					</div>

					<div class="flex flex-col gap-1">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400"
								>Confirmer le mot de passe</span
							>
							<input
								type="password"
								class="field
									{profileConfirmPassword && !profilePasswordsMatch ? 'border-rose-400 ring-2 ring-rose-200' : ''}"
								bind:value={profileConfirmPassword}
								placeholder="Répétez le mot de passe"
							/>
						</label>
						{#if profileConfirmPassword && !profilePasswordsMatch}
							<p class="text-xs text-rose-500">Les mots de passe ne correspondent pas.</p>
						{:else if profileConfirmPassword && profilePasswordsMatch}
							<p class="text-xs text-emerald-600">Les mots de passe correspondent.</p>
						{/if}
					</div>

					{#if profilePasswordError}
						<div
							class="flex items-start gap-2 text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0 mt-0.5"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
								/>
							</svg>
							{profilePasswordError}
						</div>
					{/if}
					{#if profilePasswordSuccess}
						<div
							class="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
							</svg>
							{profilePasswordSuccess}
						</div>
					{/if}

					<div class="flex justify-end pt-1">
						<button
							type="submit"
							class="btn btn-sm btn-primary disabled:opacity-50"
							disabled={!profileCanSavePassword}
						>
							{profilePasswordSubmitting ? 'Enregistrement...' : 'Mettre à jour'}
						</button>
					</div>
				</form>

				<!-- Zone de danger -->
				<div
					class="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/30 p-4 flex flex-col gap-2"
				>
					<p class="text-[10px] font-semibold uppercase tracking-widest text-rose-400">
						Zone de danger
					</p>
					{#if !profileConfirmDelete}
						<button
							type="button"
							class="flex items-center gap-2 text-sm text-rose-500 hover:text-rose-600 dark:hover:text-rose-400 transition-colors text-left"
							on:click={() => (profileConfirmDelete = true)}
						>
							<svg
								class="w-4 h-4 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
							Supprimer mon compte
						</button>
					{:else}
						<p class="text-xs text-rose-500 mb-2">
							Tous tes moniteurs seront supprimés. Cette action est irréversible.
						</p>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-rose-400"
								>Tape <strong>supprimer</strong> pour confirmer</span
							>
							<input
								type="text"
								class="rounded-lg border border-rose-300 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-400"
								bind:value={profileDeleteConfirmText}
								placeholder="supprimer"
								disabled={profileDeleting}
							/>
						</label>
						<div class="flex gap-2 justify-end mt-1">
							<button
								type="button"
								class="btn btn-sm btn-secondary"
								on:click={() => {
									profileConfirmDelete = false;
									profileDeleteConfirmText = '';
								}}
								disabled={profileDeleting}
							>
								Annuler
							</button>
							<button
								type="button"
								class="btn btn-sm bg-rose-500 hover:bg-rose-600 text-white border-transparent disabled:opacity-50"
								on:click={deleteAccount}
								disabled={profileDeleting || profileDeleteConfirmText !== 'supprimer'}
							>
								{profileDeleting ? 'Suppression...' : 'Supprimer'}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

{#if showTeams}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40 px-4"
		on:click={() => (showTeams = false)}
		role="presentation"
		use:modal={() => (showTeams = false)}
	>
		<div
			class="w-full max-w-lg rounded-2xl overflow-hidden
                   bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-soft-lg"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="px-5 pb-5 pt-5 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">
				<div class="flex items-center justify-between mb-1">
					<h2 class="text-sm font-semibold text-slate-800 dark:text-slate-100">
						Espaces &amp; équipes
					</h2>
					<button
						type="button"
						class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
						on:click={() => (showTeams = false)}
					>
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				<!-- Créer un nouvel espace (mis en avant) -->
				<div
					class="rounded-xl border border-cyan-200 dark:border-cyan-800 bg-cyan-50/60 dark:bg-cyan-900/15 shadow-sm p-4 flex flex-col gap-2"
				>
					<p class="eyebrow">Nouvel espace</p>
					<p class="text-xs text-slate-500 dark:text-slate-400 -mt-1">
						Crée un espace partagé dont tu seras l'admin. Tu pourras y inviter des membres.
					</p>
					<div class="flex items-center gap-2">
						<input
							class="flex-1 field"
							bind:value={newTeamName}
							placeholder="Nom de l'espace (ex. Production)"
							on:keydown={(e) => e.key === 'Enter' && createTeam()}
						/>
						<button type="button" class="btn btn-sm btn-primary" on:click={createTeam}>Créer</button
						>
					</div>
					{#if createTeamError}<p class="text-xs text-rose-500">{createTeamError}</p>{/if}
				</div>

				<!-- Équipe à gérer -->
				{#if $teams.length > 1}
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Espace à gérer</span>
						<select class="field" bind:value={$activeTeamId}>
							{#each $teams as t (t.id)}
								<option value={t.id}>{t.name} · {roleLabel(t.role)}</option>
							{/each}
						</select>
					</label>
				{/if}

				<!-- Gestion de l'espace actif -->
				<div
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
				>
					{#if $activeTeam}
						<div class="flex items-baseline justify-between gap-2">
							<p class="eyebrow">{$activeTeam.name}</p>
							<span class="text-[11px] text-slate-400">{roleLabel($activeRole ?? '')}</span>
						</div>
						<p class="text-xs text-slate-500 dark:text-slate-400 -mt-1">
							Les ressources appartiennent à l'espace. Les alertes vont aux destinataires des
							moniteurs/groupes, ou à défaut aux admins de l'espace.
						</p>

						{#if isTeamAdmin}
							<label class="flex flex-col gap-1">
								<span class="text-xs text-slate-500 dark:text-slate-400">Nom de l'espace</span>
								<input class="field" bind:value={teamNameDraft} />
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs text-slate-500 dark:text-slate-400"
									>Webhook d'alerte (type)</span
								>
								<select class="field" bind:value={profileWebhookKind}>
									<option value="discord">Discord</option>
									<option value="slack">Slack</option>
									<option value="ntfy">ntfy</option>
									<option value="generic">Webhook générique (JSON)</option>
								</select>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-slate-500 dark:text-slate-400"
									>URL du webhook (vide = désactivé)</span
								>
								<input
									type="url"
									class="field"
									bind:value={profileWebhookUrl}
									placeholder="https://discord.com/api/webhooks/..."
								/>
							</label>
							{#if teamSettingsError}
								<div
									class="text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
								>
									{teamSettingsError}
								</div>
							{/if}
							{#if teamSettingsSuccess}
								<div
									class="text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
								>
									{teamSettingsSuccess}
								</div>
							{/if}
							<div class="flex justify-end">
								<button
									type="button"
									class="btn btn-sm btn-primary disabled:opacity-50"
									on:click={saveTeamSettings}
									disabled={teamSettingsSubmitting}
									>{teamSettingsSubmitting ? 'Enregistrement...' : "Enregistrer l'espace"}</button
								>
							</div>
						{/if}

						<!-- Ma préférence email pour cet espace -->
						<label
							class="flex items-start gap-2.5 cursor-pointer rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2.5"
						>
							<input
								type="checkbox"
								class="mt-0.5 h-4 w-4 shrink-0 accent-cyan-500 cursor-pointer"
								bind:checked={myEmailEnabled}
								on:change={saveMyEmailPref}
							/>
							<span class="flex flex-col">
								<span class="text-sm text-slate-700 dark:text-slate-200"
									>Recevoir les alertes email pour cet espace</span
								>
								<span class="text-xs text-slate-400 dark:text-slate-500">
									{myEmailEnabled
										? `Envoyées à ${authState?.user?.email ?? 'ton adresse'} quand tu es destinataire`
										: 'Désactivé pour cet espace.'}
								</span>
							</span>
						</label>
						{#if myEmailError}<p class="text-xs text-rose-500">{myEmailError}</p>{/if}

						<!-- Membres -->
						<div class="flex flex-col gap-1.5">
							<span class="text-xs text-slate-500 dark:text-slate-400"
								>Membres ({teamMembers.length})</span
							>
							{#if !teamMembersLoaded}
								<p class="text-xs text-slate-400">Chargement…</p>
							{/if}
							{#each teamMembers as m (m.id)}
								<div class="flex items-center gap-2 text-xs">
									<span class="text-slate-700 dark:text-slate-200 truncate">{m.email}</span>
									{#if isTeamAdmin}
										<select
											class="ml-auto rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-1.5 py-1 text-[11px]"
											value={m.role}
											on:change={(e) => changeMemberRole(m.id, e.currentTarget.value)}
										>
											<option value="admin">Admin</option>
											<option value="member">Membre</option>
											<option value="readonly">Lecture seule</option>
										</select>
										<button
											type="button"
											class="text-rose-500 hover:text-rose-400"
											on:click={() => removeMember(m.id)}>retirer</button
										>
									{:else}
										<span class="ml-auto text-slate-400">{roleLabel(m.role)}</span>
									{/if}
								</div>
							{/each}
							{#if inviteError}<p class="text-xs text-rose-500">{inviteError}</p>{/if}
							{#if isTeamAdmin}
								<div class="flex items-center gap-2 mt-1">
									<input
										class="flex-1 field"
										bind:value={inviteEmail}
										placeholder="email d'un compte existant"
									/>
									<select class="field w-auto" bind:value={inviteRole}>
										<option value="member">Membre</option>
										<option value="readonly">Lecture seule</option>
										<option value="admin">Admin</option>
									</select>
									<button type="button" class="btn btn-sm btn-primary" on:click={inviteMember}
										>Inviter</button
									>
								</div>
							{/if}
						</div>

						<!-- Suppression / réactivation de l'espace -->
						{#if activeTeamScheduled}
							<div
								class="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2.5 flex flex-col gap-1.5"
							>
								<p class="text-xs font-semibold text-amber-700 dark:text-amber-400">
									⏳ Suppression programmée
								</p>
								<p class="text-xs text-amber-700/90 dark:text-amber-300/90">
									Monitoring suspendu. Suppression définitive le <strong
										>{teamPurgeDate(activeTeamScheduled)}</strong
									>. Tu peux encore réactiver cet espace d'ici là.
								</p>
								{#if isTeamAdmin}
									<div class="flex justify-end">
										<button
											type="button"
											class="btn btn-sm btn-secondary"
											on:click={restoreActiveTeam}>Réactiver l'espace</button
										>
									</div>
								{/if}
							</div>
						{:else if isTeamAdmin}
							<div
								class="border-t border-slate-200 dark:border-slate-700 pt-3 mt-1 flex flex-col gap-1.5"
							>
								<span class="text-xs font-semibold text-rose-600 dark:text-rose-400"
									>Zone de danger</span
								>
								<div class="flex items-center justify-between gap-2">
									<span class="text-xs text-slate-500 dark:text-slate-400">
										{canDeleteActiveTeam
											? 'Supprime cet espace et tout son contenu.'
											: 'Impossible de supprimer votre dernier espace actif.'}
									</span>
									<button
										type="button"
										class="btn btn-sm bg-rose-500 hover:bg-rose-600 text-white disabled:opacity-40"
										on:click={openDeleteTeam}
										disabled={!canDeleteActiveTeam}>Supprimer l'espace</button
									>
								</div>
							</div>
						{/if}
					{:else}
						<p class="text-sm text-slate-500 dark:text-slate-400">
							Aucun espace sélectionné. Crée-en un ci-dessus.
						</p>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

{#if confirmDeleteTeam && $activeTeam}
	<div
		class="fixed inset-0 z-[60] flex items-center justify-center backdrop-blur-md bg-black/50 px-4"
		on:click={() => (confirmDeleteTeam = false)}
		role="presentation"
		use:modal={() => (confirmDeleteTeam = false)}
	>
		<div
			class="w-full max-w-md rounded-2xl overflow-hidden bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-900 shadow-soft-lg"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="flex flex-col gap-3 px-5 py-5">
				<div class="flex items-center gap-3">
					<span
						class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-xl text-rose-600 dark:bg-rose-900/40 dark:text-rose-400"
						>⚠️</span
					>
					<h2 class="text-base font-semibold text-slate-800 dark:text-slate-100">
						Supprimer l'espace « {$activeTeam.name} » ?
					</h2>
				</div>
				<div
					class="flex flex-col gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-900/20 dark:text-rose-300"
				>
					<span
						>Tout le contenu de l'espace sera supprimé : <strong
							>moniteurs, groupes, destinataires, incidents et historique</strong
						>.</span
					>
					<span
						>L'espace est d'abord <strong>désactivé 7 jours</strong> (monitoring suspendu) ; tu peux
						le
						<strong>réactiver</strong> pendant ce délai. Passé 7 jours, la suppression est
						<strong>définitive et irréversible</strong>.</span
					>
				</div>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">
						Pour confirmer, écris le nom de l'espace : <strong>{$activeTeam.name}</strong>
					</span>
					<input class="field" bind:value={deleteTeamConfirmText} placeholder={$activeTeam.name} />
				</label>
				{#if deleteTeamError}<p class="text-xs text-rose-500">{deleteTeamError}</p>{/if}
				<div class="flex justify-end gap-2 pt-1">
					<button
						type="button"
						class="btn btn-sm btn-secondary"
						on:click={() => (confirmDeleteTeam = false)}>Annuler</button
					>
					<button
						type="button"
						class="btn btn-sm bg-rose-500 text-white hover:bg-rose-600 disabled:opacity-40"
						on:click={scheduleDeleteTeam}
						disabled={deleteTeamSubmitting || deleteTeamConfirmText.trim() !== $activeTeam.name}
						>{deleteTeamSubmitting ? 'Suppression...' : 'Désactiver puis supprimer'}</button
					>
				</div>
			</div>
		</div>
	</div>
{/if}
