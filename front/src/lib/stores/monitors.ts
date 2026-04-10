import { writable } from 'svelte/store';

export type MonitorStatus = 'up' | 'down' | 'checking';

export type CheckEntry = {
	id: number;
	status: 'up' | 'down';
	latency_ms: number | null;
	checked_at: string;
};

export type MonitorCardData = {
	id: number;
	name: string;
	url: string;
	status: MonitorStatus;
	type: string;
	latency: number | null;
	history: CheckEntry[];
	lastCheckedAt: string | null;
	expectedStatusCode: number;
	lastStatusCode: number | null;
	sslExpiryAt: string | null;
	createdAt: string;
};

export const monitors = writable<MonitorCardData[]>([]);
