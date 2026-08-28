import assert from "node:assert/strict";
import test from "node:test";

import { createProjectPreview, createSandboxedDocument } from "../src/utils/browser.js";

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

test("project preview combines HTML, CSS, and JavaScript in a sandbox", () => {
  const document = createProjectPreview([
    { filename: "index.html", content: "<html><head></head><body><h1>CodeX</h1></body></html>" },
    { filename: "style.css", content: "h1 { color: blue; }" },
    { filename: "script.js", content: "document.querySelector('h1').dataset.ready = 'true';" },
  ]);

  assert.match(document, /h1 \{ color: blue; \}/);
  assert.match(document, /dataset\.ready/);
  assert.match(document, /script-src 'unsafe-inline'/);
  assert.match(document, /connect-src 'none'/);
});

test("CSS-only projects do not claim to have a runnable preview", () => {
  assert.equal(createProjectPreview([{ filename: "style.css", content: "body {}" }]), null);
});
