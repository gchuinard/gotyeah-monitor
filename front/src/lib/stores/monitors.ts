import { writable } from 'svelte/store';

export type MonitorStatus = 'up' | 'down' | 'checking';

export type MonitorCardData = {
	id: number;
	name: string;
	url: string;
	status: MonitorStatus;
	type: string;
	latency: number | null;
	history: number[];
	lastCheckedAt: string | null;
	expectedStatusCode: number;
	lastStatusCode: number | null;
	createdAt: string;
};

export const monitors = writable<MonitorCardData[]>([]);
