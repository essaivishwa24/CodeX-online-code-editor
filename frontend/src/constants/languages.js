export const LANGUAGES = {
  python: {
    id: "python",
    label: "Python",
    monacoLanguage: "python",
    extension: "py",
    starter: `def greet(name):
    return f"Hello, {name}!"


print(greet("CodeX"))`,
  },
  javascript: {
    id: "javascript",
    label: "JavaScript",
    monacoLanguage: "javascript",
    extension: "js",
    starter: `const greet = (name) => \`Hello, \${name}!\`;

console.log(greet("CodeX"));`,
  },
  html: {
    id: "html",
    label: "HTML / CSS",
    monacoLanguage: "html",
    extension: "html",
    starter: `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CodeX Preview</title>
    <style>
      body {
        min-height: 100vh;
        margin: 0;
        display: grid;
        place-items: center;
        font-family: system-ui, sans-serif;
        color: #182033;
        background: #f2f4ff;
      }

      h1 { color: #6071e8; }
    </style>
  </head>
  <body>
    <main>
      <h1>Hello from CodeX!</h1>
      <p>Edit this page, then press Run to refresh the preview.</p>
    </main>
  </body>
</html>`,
  },
};

export const LANGUAGE_OPTIONS = Object.values(LANGUAGES);
export const DEFAULT_LANGUAGE = "python";

export const STORAGE_KEYS = {
  language: "codex:selected-language",
  theme: "codex:theme",
  split: "codex:editor-split",
  code: (language) => `codex:code:${language}`,
};

export function isSupportedLanguage(language) {
  return Object.prototype.hasOwnProperty.call(LANGUAGES, language);
}
