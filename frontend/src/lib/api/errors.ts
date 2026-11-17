export type FieldError = { key: string; message: string };

export type ApiErrorOptions = {
	isSetupRequired?: boolean;
	isMaintenance?: boolean;
	isOffline?: boolean;
};

/**
 * One error type for every failed request.
 *
 * The backend is not uniform: some routes answer with a string `detail`, others
 * with `{ errors: [...] }`, and a reverse proxy in front may answer with HTML.
 * Callers should never have to know which.
 */
export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;
	readonly fieldErrors: FieldError[];
	readonly stage?: string;
	readonly isSetupRequired: boolean;
	readonly isMaintenance: boolean;
	readonly isOffline: boolean;

	constructor(
		status: number,
		detail: string,
		fieldErrors: FieldError[] = [],
		options: ApiErrorOptions = {},
		stage?: string
	) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
		this.fieldErrors = fieldErrors;
		this.stage = stage;
		this.isSetupRequired = options.isSetupRequired ?? false;
		this.isMaintenance = options.isMaintenance ?? false;
		this.isOffline = options.isOffline ?? false;
	}

	/** The backend could not be reached at all. */
	static offline(): ApiError {
		return new ApiError(0, 'Tidak dapat terhubung ke backend', [], { isOffline: true });
	}

	fieldError(key: string): string | undefined {
		return this.fieldErrors.find((entry) => entry.key === key)?.message;
	}
}

type JsonBody = Record<string, unknown>;

async function readJson(response: Response): Promise<JsonBody | null> {
	const contentType = response.headers.get('content-type') ?? '';
	if (!contentType.includes('application/json')) {
		return null;
	}
	try {
		const parsed = await response.json();
		return parsed && typeof parsed === 'object' ? (parsed as JsonBody) : null;
	} catch {
		return null;
	}
}

export async function toApiError(response: Response): Promise<ApiError> {
	const body = await readJson(response);
	const status = response.status;

	// A proxy error page (HTML) must not become the message shown to the user.
	const statusText = response.statusText || 'Terjadi kesalahan';

	let detail = statusText;
	let fieldErrors: FieldError[] = [];
	let stage: string | undefined;
	let isSetupRequired = false;
	let isMaintenance = status === 503;

	if (body) {
		const rawDetail = body.detail;

		if (typeof rawDetail === 'string') {
			detail = rawDetail;
		} else if (rawDetail && typeof rawDetail === 'object') {
			const container = rawDetail as JsonBody;
			if (Array.isArray(container.errors)) {
				fieldErrors = (container.errors as FieldError[]).filter(
					(entry) => entry && typeof entry.key === 'string' && typeof entry.message === 'string'
				);
			}
			if (typeof container.stage === 'string') {
				stage = container.stage;
			}
			if (typeof container.message === 'string') {
				detail = container.message;
			}
		}

		if (typeof body.message === 'string' && body.message) {
			detail = body.message;
		}
		if (status === 409 && body.setup_required === true) {
			isSetupRequired = true;
		}
		if (body.detail === 'maintenance') {
			isMaintenance = true;
		}
	}

	return new ApiError(status, detail, fieldErrors, { isSetupRequired, isMaintenance }, stage);
}
