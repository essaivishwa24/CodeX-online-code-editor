import assert from "node:assert/strict";
import test from "node:test";

import { filenameForLanguage, languageForFilename, LANGUAGES, LANGUAGE_OPTIONS, languageOptionLabel } from "../src/constants/languages.js";

test("all required languages have Monaco mappings, extensions, and distinct starters", () => {
  assert.deepEqual(LANGUAGE_OPTIONS.map((item) => item.id), [
    "python", "javascript", "typescript", "java", "c", "cpp", "sql", "html", "css",
  ]);
  for (const language of LANGUAGE_OPTIONS) {
    assert.ok(language.monacoLanguage);
    assert.ok(language.extension);
    assert.ok(language.starter);
  }
  assert.match(LANGUAGES.java.starter, /public class Main/);
  assert.match(LANGUAGES.cpp.starter, /iostream/);
  assert.match(LANGUAGES.sql.starter, /CREATE TABLE/);
  assert.match(LANGUAGES.css.starter, /color: blue/);
});

test("Java and C labels reflect backend runtime availability", () => {
  const statuses = {
    java: { available: false, detail: "JDK not detected" },
    c: { available: true, detail: "Ready" },
  };

  assert.equal(languageOptionLabel(LANGUAGES.java, statuses), "Java — JDK not detected");
  assert.equal(languageOptionLabel(LANGUAGES.c, statuses), "C — Ready");
  assert.equal(languageOptionLabel(LANGUAGES.python, statuses), "Python");
});

test("file extensions infer the correct editor language", () => {
  assert.equal(languageForFilename("main.py"), "python");
  assert.equal(languageForFilename("component.jsx"), "javascript");
  assert.equal(languageForFilename("component.tsx"), "typescript");
  assert.equal(languageForFilename("Main.java"), "java");
  assert.equal(languageForFilename("main.c"), "c");
  assert.equal(languageForFilename("main.cc"), "cpp");
  assert.equal(languageForFilename("query.sql"), "sql");
  assert.equal(languageForFilename("index.htm"), "html");
  assert.equal(languageForFilename("style.css"), "css");
  assert.equal(filenameForLanguage("main.py", "cpp"), "main.cpp");
  assert.equal(filenameForLanguage("anything.txt", "java"), "Main.java");
  assert.equal(filenameForLanguage("anything.txt", "sql"), "query.sql");
});
