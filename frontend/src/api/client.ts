import type {
  HealthResponse,
  LeadDiscoveryRequest,
  LeadDiscoveryResponse,
} from './types';

const API_BASE_STORAGE_KEY = 'leadfinder.apiBase';

function resolveApiBase(): string {
  try {
    const stored = window.localStorage.getItem(API_BASE_STORAGE_KEY);
    if (stored && stored.trim()) return stored.trim().replace(/\/+$/, '');
  } catch {
    /* storage unavailable */
  }
  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return fromEnv ?? 'http://127.0.0.1:8000';
}

const API_BASE: string = resolveApiBase();

export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string>;

  constructor(
    message: string,
    status: number,
    fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

interface FastApiDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

function parseFieldErrors(detail: unknown): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  if (!Array.isArray(detail)) return fieldErrors;
  for (const item of detail as FastApiDetail[]) {
    if (!item || typeof item !== 'object') continue;
    const loc = item.loc ?? [];
    const field = loc
      .filter((part) => typeof part === 'string' && part !== 'body')
      .join('.');
    const key = field || '_';
    if (!fieldErrors[key]) {
      fieldErrors[key] = item.msg ?? 'Invalid value';
    }
  }
  return fieldErrors;
}

function detailMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  const fieldErrors = parseFieldErrors(detail);
  const messages = Object.values(fieldErrors);
  if (messages.length > 0) return messages.join(' ');
  return 'Request failed validation.';
}

export async function discoverLeads(
  payload: LeadDiscoveryRequest,
  signal?: AbortSignal,
): Promise<LeadDiscoveryResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/leads/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Start it with: uvicorn app.main:app --reload`,
      0,
    );
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body.detail;
    } catch {
      detail = null;
    }
    throw new ApiError(
      detailMessage(detail) || `Request failed (HTTP ${response.status}).`,
      response.status,
      parseFieldErrors(detail),
    );
  }

  return (await response.json()) as LeadDiscoveryResponse;
}

export async function checkHealth(
  signal?: AbortSignal,
): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`, { signal });
  if (!response.ok) {
    throw new Error(`Health check failed (HTTP ${response.status})`);
  }
  return (await response.json()) as HealthResponse;
}

export { API_BASE };
