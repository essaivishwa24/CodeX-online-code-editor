import assert from "node:assert/strict";
import test from "node:test";

import { createSandboxedDocument } from "../src/utils/browser.js";

test("preview documents receive the restrictive policy inside head", () => {
  const document = createSandboxedDocument("<!doctype html><html><head><title>Demo</title></head><body>Hi</body></html>");

  assert.match(document, /Content-Security-Policy/);
  assert.match(document, /script-src 'none'/);
  assert.match(document, /form-action 'none'/);
  assert.ok(document.indexOf("Content-Security-Policy") < document.indexOf("<title>"));
});

test("HTML fragments are wrapped in a complete protected document", () => {
  const document = createSandboxedDocument("<h1>Hello</h1>");

  assert.match(document, /^<!doctype html><html><head>/);
  assert.match(document, /<body><h1>Hello<\/h1><\/body><\/html>$/);
});
