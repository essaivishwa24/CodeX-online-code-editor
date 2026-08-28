export const LANGUAGES = {
  python: { id: "python", label: "Python", monacoLanguage: "python", extension: "py", starter: 'print("Hello from CodeX")' },
  javascript: { id: "javascript", label: "JavaScript", monacoLanguage: "javascript", extension: "js", starter: 'console.log("Hello from CodeX");' },
  typescript: { id: "typescript", label: "TypeScript", monacoLanguage: "typescript", extension: "ts", starter: 'const message: string = "Hello from CodeX";\nconsole.log(message);' },
  java: { id: "java", label: "Java", monacoLanguage: "java", extension: "java", starter: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello from CodeX");\n    }\n}' },
  c: { id: "c", label: "C", monacoLanguage: "c", extension: "c", starter: '#include <stdio.h>\n\nint main() {\n    printf("Hello from CodeX\\n");\n    return 0;\n}' },
  cpp: { id: "cpp", label: "C++", monacoLanguage: "cpp", extension: "cpp", starter: '#include <iostream>\n\nint main() {\n    std::cout << "Hello from CodeX" << std::endl;\n    return 0;\n}' },
  sql: { id: "sql", label: "SQL", monacoLanguage: "sql", extension: "sql", starter: "CREATE TABLE users (\n    id INTEGER PRIMARY KEY,\n    name TEXT NOT NULL\n);\n\nINSERT INTO users (name) VALUES ('Ada'), ('Grace');\n\nSELECT * FROM users ORDER BY id;" },
  html: { id: "html", label: "HTML", monacoLanguage: "html", extension: "html", starter: '<!DOCTYPE html>\n<html>\n<head>\n    <title>CodeX</title>\n</head>\n<body>\n    <h1>Hello from CodeX</h1>\n</body>\n</html>' },
  css: { id: "css", label: "CSS", monacoLanguage: "css", extension: "css", starter: 'body {\n    font-family: Arial, sans-serif;\n}\n\nh1 {\n    color: blue;\n}' },
};

export const LANGUAGE_OPTIONS = Object.values(LANGUAGES);
export const DEFAULT_LANGUAGE = "python";

const EXTENSION_LANGUAGES = {
  py: "python", js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  java: "java", c: "c", cpp: "cpp", cc: "cpp", sql: "sql", html: "html", htm: "html", css: "css",
};

export function languageForFilename(filename, fallback = DEFAULT_LANGUAGE) {
  const extension = filename?.split(".").pop()?.toLowerCase();
  return EXTENSION_LANGUAGES[extension] || fallback;
}

export function filenameForLanguage(filename, language) {
  const config = LANGUAGES[language];
  if (!config) return filename;
  const preferredBase = language === "java" ? "Main" : language === "sql" ? "query" : null;
  const base = filename?.replace(/\.[^.]+$/, "") || preferredBase || "main";
  return `${preferredBase || base}.${config.extension}`;
}

export const STORAGE_KEYS = {
  language: "codex:selected-language",
  theme: "codex:theme",
  split: "codex:editor-split",
  code: (language) => `codex:code:${language}`,
  sqlWorkspace: (projectId, fileId) => `codex:sql-workspace:${projectId}:${fileId}`,
};

export function isSupportedLanguage(language) {
  return Object.prototype.hasOwnProperty.call(LANGUAGES, language);
}

export function languageOptionLabel(language, runtimeStatuses = {}) {
  if (language.id !== "java" && language.id !== "c") return language.label;
  const runtime = runtimeStatuses[language.id];
  if (!runtime) return language.label;
  return `${language.label} — ${runtime.available ? "Ready" : runtime.detail}`;
}
