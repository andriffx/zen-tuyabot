import { get } from './client';
import type { ActivityLog, ErrorLog, LogPage, PowerLog } from './types';

export type LogQuery = { limit?: number; offset?: number; deviceId?: number };

function query(params: LogQuery): string {
	const search = new URLSearchParams();
	if (params.limit !== undefined) search.set('limit', String(params.limit));
	if (params.offset !== undefined) search.set('offset', String(params.offset));
	if (params.deviceId !== undefined) search.set('device_id', String(params.deviceId));
	const rendered = search.toString();
	return rendered ? `?${rendered}` : '';
}

export const logsApi = {
	activities: (params: LogQuery = {}) => get<LogPage<ActivityLog>>(`/api/logs/activities${query(params)}`),
	power: (params: LogQuery = {}) => get<LogPage<PowerLog>>(`/api/logs/power${query(params)}`),
	errors: (params: LogQuery = {}) =>
		get<LogPage<ErrorLog>>(`/api/logs/errors${query({ limit: params.limit, offset: params.offset })}`)
};
