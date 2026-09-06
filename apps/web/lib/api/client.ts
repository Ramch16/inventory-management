/**
 * Typed API client.
 *
 * Session tokens live in HttpOnly cookies, so requests are sent with
 * `credentials: "include"` and the CSRF token is echoed from its readable cookie
 * into the header the API expects.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const API_PREFIX = "/api/v1";

const CSRF_COOKIE = "ja_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** Field-level messages produced by request validation. */
  get fieldErrors(): Array<{ field: string; message: string }> {
    const fields = this.details.fields;
    return Array.isArray(fields) ? (fields as Array<{ field: string; message: string }>) : [];
  }
}

function readCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Send a FormData body untouched (file uploads). */
  formData?: FormData;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, formData, headers, ...rest } = options;
  const method = rest.method ?? (body || formData ? "POST" : "GET");

  const requestHeaders = new Headers(headers);
  if (!formData && body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }
  const csrf = readCsrfCookie();
  if (csrf && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    requestHeaders.set(CSRF_HEADER, csrf);
  }

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    ...rest,
    method,
    headers: requestHeaders,
    credentials: "include",
    body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const errorBody: ApiErrorBody = payload?.error ?? {
      code: "unknown_error",
      message: response.statusText || "Request failed",
    };
    throw new ApiError(response.status, errorBody);
  }

  return payload as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  delete: <T,>(path: string, body?: unknown) => request<T>(path, { method: "DELETE", body }),
  upload: <T,>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", formData }),
};
