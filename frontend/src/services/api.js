// Keep this value as the backend origin only. Every endpoint below owns its
// complete `/api/...` path so production cannot accidentally create `/api/api`.
const PRODUCTION_API_URL = "https://codex-backend-ksz8.onrender.com";
const configuredBaseUrl = (import.meta.env?.VITE_API_URL || "").trim().replace(/\/$/, "");
const isProduction = Boolean(import.meta.env?.PROD);
const configuredProductionUrl = configuredBaseUrl === PRODUCTION_API_URL ? configuredBaseUrl : PRODUCTION_API_URL;
export const API_BASE_URL = isProduction ? configuredProductionUrl : configuredBaseUrl;

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

const TOKEN_KEY = "codex_access_token";
const LEGACY_TOKEN_KEYS = ["codex:token"];

function authStorage() {
  if (typeof window !== "undefined" && window.sessionStorage) {
    return window.sessionStorage;
  }
  return localStorage;
}

export function getToken() {
  const storage = authStorage();
  const currentToken = storage.getItem(TOKEN_KEY);
  if (currentToken) return currentToken;

  for (const legacyKey of LEGACY_TOKEN_KEYS) {
    const legacyToken = storage.getItem(legacyKey);
    if (legacyToken) {
      storage.setItem(TOKEN_KEY, legacyToken);
      storage.removeItem(legacyKey);
      return legacyToken;
    }
  }
  return null;
}

export function setToken(token) {
  const storage = authStorage();
  for (const legacyKey of LEGACY_TOKEN_KEYS) storage.removeItem(legacyKey);
  if (token) storage.setItem(TOKEN_KEY, token);
  else storage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const token = getToken();
  try {
    const url = apiUrl(path);
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(
        readableDetail(body.detail || body.error),
        response.status === 401 ? "UNAUTHORIZED" : "HTTP_ERROR",
        response.status,
        url,
      );
    }
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Unable to contact the CodeX API.", "NETWORK_ERROR");
  }
}
export const register = (data) => request("/api/auth/register", { method: "POST", body: JSON.stringify(data) });
export const login = (data) => request("/api/auth/login", { method: "POST", body: JSON.stringify(data) });
export const getCurrentUser = () => request("/api/auth/me");
export const logout = () => request("/api/auth/logout", { method: "POST" });
export const listProjects = () => request("/api/projects");
export const createProject = (data) => request("/api/projects", { method: "POST", body: JSON.stringify(data) });
export const getProject = (id) => request(`/api/projects/${id}`);
export const updateProject = (id, data) => request(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteProject = (id) => request(`/api/projects/${id}`, { method: "DELETE" });
export const saveFile = (projectId, fileId, data) => request(`/api/projects/${projectId}/files/${fileId}`, { method: "PATCH", body: JSON.stringify(data) });
export const createFile = (projectId, data) => request(`/api/projects/${projectId}/files`, { method: "POST", body: JSON.stringify(data) });
export const getRuntimeStatus = () => request("/api/runtime-status");
export const resetSqlPlayground = (workspaceId) => request("/api/sql/reset", {
  method: "POST",
  body: JSON.stringify({ workspace_id: workspaceId }),
});

const parsedTimeout = Number(import.meta.env?.VITE_API_TIMEOUT_MS);
const REQUEST_TIMEOUT_MS = Number.isFinite(parsedTimeout) && parsedTimeout > 0
  ? Math.max(parsedTimeout, 30_000)
  : 30_000;
const CONNECTION_ERROR_MESSAGE = "Unable to contact the CodeX API.";

export class ApiError extends Error {
  constructor(message, code = "API_ERROR", status = null, url = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.url = url;
  }
}

function connectionError(status = null) {
  return new ApiError(CONNECTION_ERROR_MESSAGE, "NETWORK_ERROR", status);
}

function readableDetail(detail) {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .filter(Boolean)
      .join("; ");
  }

  if (detail && typeof detail === "object") {
    return detail.message || detail.error || JSON.stringify(detail);
  }

  return "The server could not process this request.";
}

function normalizeResult(payload) {
  const success = payload?.success === true;
  const rawDuration =
    payload?.execution_time_ms ?? payload?.duration_ms ?? payload?.execution_time ?? null;
  const duration = rawDuration === null || rawDuration === "" ? null : Number(rawDuration);

  return {
    success,
    status: payload?.status || (success ? "success" : "runtime_error"),
    stdout: typeof payload?.stdout === "string" ? payload.stdout : (typeof payload?.output === "string" ? payload.output : ""),
    stderr: typeof payload?.stderr === "string" ? payload.stderr : (success ? "" : readableDetail(payload?.error || payload?.detail)),
    output: typeof payload?.stdout === "string" ? payload.stdout : (typeof payload?.output === "string" ? payload.output : ""),
    error: success ? "" : (typeof payload?.stderr === "string" ? payload.stderr : readableDetail(payload?.error || payload?.detail)),
    exitCode: Number.isInteger(payload?.exit_code) ? payload.exit_code : null,
    memoryUsage: Number.isFinite(payload?.memory_usage) ? payload.memory_usage : null,
    columns: Array.isArray(payload?.columns) ? payload.columns.map(String) : null,
    rows: Array.isArray(payload?.rows) ? payload.rows : null,
    rowCount: Number.isInteger(payload?.row_count) ? payload.row_count : null,
    message: typeof payload?.message === "string" ? payload.message : null,
    executionTimeMs: duration !== null && Number.isFinite(duration)
      ? (payload?.execution_time_ms != null || payload?.duration_ms != null ? duration : duration * 1000)
      : null,
  };
}

export async function executeCode({ language, code, stdin = "", workspaceId = "default" }, { signal } = {}) {
  const executionLanguage = typeof language === "string" && language.trim().toLowerCase() === "sql"
    ? "sql"
    : language;
  const requestController = new AbortController();
  let didTimeout = false;
  const timeoutId = window.setTimeout(() => {
    didTimeout = true;
    requestController.abort();
  }, REQUEST_TIMEOUT_MS);

  const abortFromCaller = () => requestController.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });

  try {
    const url = apiUrl("/api/run");
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ language: executionLanguage, code, stdin, workspace_id: workspaceId }),
      signal: requestController.signal,
    });

    const bodyText = await response.text();
    const hasResponseBody = bodyText.trim().length > 0;
    let payload = {};

    if (hasResponseBody) {
      try {
        payload = JSON.parse(bodyText);
      } catch {
        if (response.status >= 500) {
          throw connectionError(response.status);
        }

        throw new ApiError("The backend returned an unreadable response.", "INVALID_RESPONSE", response.status);
      }
    }

    if (!hasResponseBody && response.status >= 500) {
      throw connectionError(response.status);
    }

    if (!response.ok) {
      const message = readableDetail(payload?.detail || payload?.error);
      throw new ApiError(message, "HTTP_ERROR", response.status, url);
    }

    return normalizeResult(payload);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error?.name === "AbortError") {
      if (didTimeout) {
        throw new ApiError(
          "Execution took too long. The request was stopped; try a smaller program.",
          "TIMEOUT",
        );
      }

      throw new ApiError("Execution was cancelled.", "CANCELLED");
    }

    throw connectionError();
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}
