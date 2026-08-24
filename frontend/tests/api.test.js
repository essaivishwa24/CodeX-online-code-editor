import assert from "node:assert/strict";
import test from "node:test";

import { executeCode } from "../src/services/api.js";

globalThis.window = globalThis;

function jsonResponse(payload, options = {}) {
  return new Response(JSON.stringify(payload), {
    status: options.status ?? 200,
    headers: { "Content-Type": "application/json" },
  });
}

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the CodeX execution server. Make sure the backend is running.";

test("omitted execution duration stays null", async (context) => {
  context.mock.method(globalThis, "fetch", async () =>
    jsonResponse({ success: true, output: "Hello" }),
  );

  const result = await executeCode({ language: "python", code: "print('Hello')" });

  assert.deepEqual(result, {
    success: true,
    output: "Hello",
    error: "",
    executionTimeMs: null,
  });
});

test("numeric execution duration is preserved", async (context) => {
  context.mock.method(globalThis, "fetch", async () =>
    jsonResponse({ success: true, output: "Done", execution_time_ms: 12.5 }),
  );

  const result = await executeCode({ language: "javascript", code: "console.log('Done')" });

  assert.equal(result.executionTimeMs, 12.5);
});

test("backend validation details become a readable API error", async (context) => {
  context.mock.method(globalThis, "fetch", async () =>
    jsonResponse({ detail: [{ msg: "Code must not be empty" }] }, { status: 422 }),
  );

  await assert.rejects(
    executeCode({ language: "python", code: "" }),
    (error) => error.code === "HTTP_ERROR" && error.status === 422 && /must not be empty/.test(error.message),
  );
});

test("a rejected proxy request is reported as a connection error", async (context) => {
  context.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("fetch failed");
  });

  await assert.rejects(
    executeCode({ language: "python", code: "print('Hello')" }),
    (error) => error.code === "NETWORK_ERROR" && error.message === CONNECTION_ERROR_MESSAGE,
  );
});

test("an empty proxy 5xx response is reported as a connection error", async (context) => {
  context.mock.method(globalThis, "fetch", async () => new Response(null, { status: 502 }));

  await assert.rejects(
    executeCode({ language: "python", code: "print('Hello')" }),
    (error) =>
      error.code === "NETWORK_ERROR" &&
      error.status === 502 &&
      error.message === CONNECTION_ERROR_MESSAGE,
  );
});

test("a non-JSON proxy 5xx response is reported as a connection error", async (context) => {
  context.mock.method(
    globalThis,
    "fetch",
    async () => new Response("Bad Gateway", { status: 500, headers: { "Content-Type": "text/plain" } }),
  );

  await assert.rejects(
    executeCode({ language: "javascript", code: "console.log('Hello')" }),
    (error) =>
      error.code === "NETWORK_ERROR" &&
      error.status === 500 &&
      error.message === CONNECTION_ERROR_MESSAGE,
  );
});

test("a backend execution error is preserved", async (context) => {
  const executionError = "ReferenceError: missingValue is not defined";
  context.mock.method(globalThis, "fetch", async () =>
    jsonResponse({ success: false, output: "", error: executionError }),
  );

  const result = await executeCode({ language: "javascript", code: "missingValue" });

  assert.equal(result.success, false);
  assert.equal(result.error, executionError);
});
