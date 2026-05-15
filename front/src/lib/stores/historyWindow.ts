import { writable } from 'svelte/store';

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
const VALID_VALUES = HISTORY_WINDOW_PRESETS.map((p) => p.value);

function getInitial(): number {
	if (typeof window === 'undefined') return DEFAULT_HOURS;
	const raw = window.localStorage.getItem(STORAGE_KEY);
	if (raw === null) return DEFAULT_HOURS;
	const parsed = Number.parseInt(raw, 10);
	if (!Number.isFinite(parsed) || !VALID_VALUES.includes(parsed)) return DEFAULT_HOURS;
	return parsed;
}

export const historyWindowHours = writable<number>(getInitial());

if (typeof window !== 'undefined') {
	historyWindowHours.subscribe((value) => {
		window.localStorage.setItem(STORAGE_KEY, String(value));
	});
}
