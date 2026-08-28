import assert from "node:assert/strict";
import test from "node:test";

import { getCurrentUser, getToken, logout, setToken } from "../src/services/api.js";

const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  removeItem: (key) => storage.delete(key),
  setItem: (key, value) => storage.set(key, String(value)),
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("auth token uses one key and migrates the legacy key", () => {
  storage.clear();
  storage.set("codex:token", "legacy-token");

  assert.equal(getToken(), "legacy-token");
  assert.equal(storage.get("codex_access_token"), "legacy-token");
  assert.equal(storage.has("codex:token"), false);

  setToken(null);
  assert.equal(getToken(), null);
});

test("/auth/me and logout centrally send the bearer token", async (context) => {
  storage.clear();
  setToken("test-jwt");
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith("/api/auth/me")) {
      return jsonResponse({ id: 1, username: "codextest", email: "codextest@example.com", role: "user" });
    }
    return jsonResponse({ ok: true });
  });

  const user = await getCurrentUser();
  await logout();

  assert.equal(user.username, "codextest");
  assert.equal(calls.length, 2);
  assert.equal(calls[0].options.headers.Authorization, "Bearer test-jwt");
  assert.equal(calls[1].options.headers.Authorization, "Bearer test-jwt");
  assert.equal(calls[1].options.method, "POST");
});

test("auth network failures have a stable user-facing error", async (context) => {
  storage.clear();
  context.mock.method(globalThis, "fetch", async () => { throw new TypeError("fetch failed"); });

  await assert.rejects(
    getCurrentUser(),
    (error) => error.code === "NETWORK_ERROR" && error.message === "Unable to contact the CodeX API.",
  );
});
