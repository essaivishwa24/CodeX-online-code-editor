import assert from "node:assert/strict";
import test from "node:test";

import { executeCode, getRuntimeStatus, resetSqlPlayground } from "../src/services/api.js";

globalThis.window = globalThis;
globalThis.localStorage = {
  getItem: () => null,
  removeItem: () => {},
  setItem: () => {},
};

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
    status: "success",
    stdout: "Hello",
    stderr: "",
    output: "Hello",
    error: "",
    exitCode: null,
    memoryUsage: null,
    columns: null,
    rows: null,
    rowCount: null,
    message: null,
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

test("structured execution responses and stdin are preserved", async (context) => {
  let requestBody;
  context.mock.method(globalThis, "fetch", async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return jsonResponse({
      success: true,
      status: "success",
      stdout: "Hello CodeX",
      stderr: "",
      exit_code: 0,
      execution_time: 0.125,
      memory_usage: null,
    });
  });

  const result = await executeCode({
    language: "python",
    code: "name=input(); print('Hello', name)",
    stdin: "CodeX",
  });

  assert.equal(requestBody.stdin, "CodeX");
  assert.equal(result.stdout, "Hello CodeX");
  assert.equal(result.exitCode, 0);
  assert.equal(result.executionTimeMs, 125);
});

test("SQL workspace and structured table results are preserved", async (context) => {
  let requestBody;
  context.mock.method(globalThis, "fetch", async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return jsonResponse({
      success: true,
      status: "success",
      columns: ["id", "name"],
      rows: [[1, "Ada"]],
      row_count: 1,
      message: "Query returned 1 row(s).",
      execution_time: 0.01,
    });
  });

  const result = await executeCode({
    language: "sql",
    code: "SELECT 1;",
    workspaceId: "workspace-one",
  });

  assert.equal(requestBody.workspace_id, "workspace-one");
  assert.deepEqual(result.columns, ["id", "name"]);
  assert.deepEqual(result.rows, [[1, "Ada"]]);
  assert.equal(result.rowCount, 1);
});

test("SQL reset targets the selected isolated workspace", async (context) => {
  let requestBody;
  context.mock.method(globalThis, "fetch", async (url, options) => {
    assert.match(url, /\/api\/sql\/reset$/);
    requestBody = JSON.parse(options.body);
    return jsonResponse({ success: true, message: "SQL playground reset." });
  });

  const result = await resetSqlPlayground("workspace-one");

  assert.equal(requestBody.workspace_id, "workspace-one");
  assert.equal(result.success, true);
});

test("runtime status is fetched from the backend without hardcoded language flags", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => {
    assert.match(url, /\/api\/runtime-status$/);
    return jsonResponse({
      runtimes: {
        java: { available: false, detail: "JDK not detected" },
        c: { available: true, detail: "Ready" },
      },
    });
  });

  const result = await getRuntimeStatus();

  assert.equal(result.runtimes.java.available, false);
  assert.equal(result.runtimes.c.available, true);
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
