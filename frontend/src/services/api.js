const configuredBaseUrl = (import.meta.env?.VITE_API_BASE_URL || "").trim();
export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");

const parsedTimeout = Number(import.meta.env?.VITE_API_TIMEOUT_MS);
const REQUEST_TIMEOUT_MS = Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : 20_000;
const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the CodeX execution server. Make sure the backend is running.";

export class ApiError extends Error {
  constructor(message, code = "API_ERROR", status = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
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
    output: typeof payload?.output === "string" ? payload.output : "",
    error: success ? "" : readableDetail(payload?.error || payload?.detail),
    executionTimeMs: duration !== null && Number.isFinite(duration) ? duration : null,
  };
}

export async function executeCode({ language, code }, { signal } = {}) {
  const requestController = new AbortController();
  let didTimeout = false;
  const timeoutId = window.setTimeout(() => {
    didTimeout = true;
    requestController.abort();
  }, REQUEST_TIMEOUT_MS);

  const abortFromCaller = () => requestController.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });

  try {
    const response = await fetch(`${API_BASE_URL}/api/run`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ language, code }),
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
      throw new ApiError(message, "HTTP_ERROR", response.status);
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
