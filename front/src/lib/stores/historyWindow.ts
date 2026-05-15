import { writable, type Writable } from 'svelte/store';

export type HistoryWindowPreset = { value: number; label: string };

export const HISTORY_WINDOW_PRESETS: HistoryWindowPreset[] = [
	{ value: 1, label: '1h' },
	{ value: 2, label: '2h' },
	{ value: 3, label: '3h' },
	{ value: 6, label: '6h' },
	{ value: 12, label: '12h' },
	{ value: 24, label: '1j' },
	{ value: 48, label: '2j' },
	{ value: 72, label: '3j' },
	{ value: 168, label: '7j' }
];

const STORAGE_KEY = 'historyWindowHours';
const DEFAULT_HOURS = 2;
const VALID_VALUES = new Set(HISTORY_WINDOW_PRESETS.map((p) => p.value));

type WindowMap = Record<string, number>;

function load(): WindowMap {
	if (typeof window === 'undefined') return {};
	const raw = window.localStorage.getItem(STORAGE_KEY);
	if (!raw) return {};
	try {
		const parsed = JSON.parse(raw);
		if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
		const out: WindowMap = {};
		for (const [k, v] of Object.entries(parsed)) {
			if (typeof v === 'number' && VALID_VALUES.has(v)) out[k] = v;
		}
		return out;
	} catch {
		return {};
	}
}

const windowMap = writable<WindowMap>(load());

if (typeof window !== 'undefined') {
	windowMap.subscribe((value) => {
		window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
	});
}

export function monitorWindowStore(monitorId: number | string): Writable<number> {
	const key = String(monitorId);
	return {
		subscribe: (run, invalidate) =>
			windowMap.subscribe((m) => run(m[key] ?? DEFAULT_HOURS), invalidate),
		set: (value: number) => {
			if (!VALID_VALUES.has(value)) return;
			windowMap.update((m) => ({ ...m, [key]: value }));
		},
		update: (updater) => {
			windowMap.update((m) => {
				const next = updater(m[key] ?? DEFAULT_HOURS);
				if (!VALID_VALUES.has(next)) return m;
				return { ...m, [key]: next };
			});
		}
	};
}
