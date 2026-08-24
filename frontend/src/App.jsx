import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CodeEditor from "./components/CodeEditor";
import Header from "./components/Header";
import OutputConsole from "./components/OutputConsole";
import PreviewPanel from "./components/PreviewPanel";
import Toast from "./components/Toast";
import Workspace from "./components/Workspace";
import {
  DEFAULT_LANGUAGE,
  LANGUAGES,
  LANGUAGE_OPTIONS,
  STORAGE_KEYS,
  isSupportedLanguage,
} from "./constants/languages";
import { ApiError, executeCode } from "./services/api";
import { copyText, createSandboxedDocument, downloadText } from "./utils/browser";
import { readStorage, writeStorage } from "./utils/storage";

const EMPTY_RUN_STATE = {
  status: "idle",
  output: "",
  error: "",
  executionTimeMs: null,
};

function initialLanguage() {
  const saved = readStorage(STORAGE_KEYS.language, DEFAULT_LANGUAGE);
  return isSupportedLanguage(saved) ? saved : DEFAULT_LANGUAGE;
}

function initialDrafts() {
  return Object.fromEntries(
    LANGUAGE_OPTIONS.map((item) => {
      const stored = readStorage(STORAGE_KEYS.code(item.id), null);
      return [item.id, stored === null ? item.starter : stored];
    }),
  );
}

function initialTheme() {
  const saved = readStorage(STORAGE_KEYS.theme, "dark");
  return saved === "light" ? "light" : "dark";
}

export default function App() {
  const [language, setLanguage] = useState(initialLanguage);
  const [drafts, setDrafts] = useState(initialDrafts);
  const [theme, setTheme] = useState(initialTheme);
  const [runState, setRunState] = useState(EMPTY_RUN_STATE);
  const [previewDocument, setPreviewDocument] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [toast, setToast] = useState(null);

  const requestIdRef = useRef(0);
  const requestControllerRef = useRef(null);
  const runLockRef = useRef(false);

  const selectedLanguage = LANGUAGES[language];
  const code = drafts[language] ?? "";
  const isRunning = runState.status === "running";

  const showToast = useCallback((message, type = "success") => {
    setToast({ id: Date.now(), message, type });
  }, []);

  useEffect(() => {
    if (!toast) return undefined;
    const timeoutId = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content",
      theme === "dark" ? "#0b0d12" : "#f3f5f9",
    );
    writeStorage(STORAGE_KEYS.theme, theme);
  }, [theme]);

  useEffect(() => {
    writeStorage(STORAGE_KEYS.language, language);
  }, [language]);

  useEffect(() => {
    document.body.classList.toggle("editor-is-fullscreen", isFullscreen);
    const handleEscape = (event) => {
      if (event.key === "Escape" && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("keydown", handleEscape);
      document.body.classList.remove("editor-is-fullscreen");
    };
  }, [isFullscreen]);

  const cancelActiveRun = useCallback(() => {
    requestIdRef.current += 1;
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    runLockRef.current = false;
  }, []);

  const runCode = useCallback(async () => {
    if (runLockRef.current) return;

    const submittedLanguage = language;
    const submittedCode = drafts[submittedLanguage] ?? "";

    if (!isSupportedLanguage(submittedLanguage)) {
      setRunState({
        ...EMPTY_RUN_STATE,
        status: "error",
        error: "This language is not supported by CodeX.",
      });
      return;
    }

    if (!submittedCode.trim()) {
      setRunState({
        ...EMPTY_RUN_STATE,
        status: "error",
        error: "The editor is empty. Add some code before running it.",
      });
      return;
    }

    runLockRef.current = true;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const startedAt = performance.now();
    setRunState({ ...EMPTY_RUN_STATE, status: "running" });

    try {
      if (submittedLanguage === "html") {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        if (requestId !== requestIdRef.current) return;

        setPreviewDocument(createSandboxedDocument(submittedCode));
        setRunState({
          status: "success",
          output: "Preview refreshed. Embedded scripts and form submissions are blocked for safety.",
          error: "",
          executionTimeMs: performance.now() - startedAt,
        });
        return;
      }

      const controller = new AbortController();
      requestControllerRef.current = controller;
      const result = await executeCode(
        { language: submittedLanguage, code: submittedCode },
        { signal: controller.signal },
      );

      if (requestId !== requestIdRef.current) return;

      if (result.success) {
        setRunState({
          status: "success",
          output: result.output,
          error: "",
          executionTimeMs: result.executionTimeMs ?? performance.now() - startedAt,
        });
      } else {
        setRunState({
          status: "error",
          output: "",
          error: result.error || "The program could not be executed.",
          executionTimeMs: result.executionTimeMs,
        });
      }
    } catch (error) {
      if (requestId !== requestIdRef.current || error?.code === "CANCELLED") return;
      const message =
        error instanceof ApiError
          ? error.message
          : "Something unexpected happened while running your code. Please try again.";
      setRunState({
        status: "error",
        output: "",
        error: message,
        executionTimeMs: null,
      });
    } finally {
      if (requestId === requestIdRef.current) {
        requestControllerRef.current = null;
        runLockRef.current = false;
      }
    }
  }, [drafts, language]);

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        void runCode();
      }
    };
    window.addEventListener("keydown", handleShortcut, true);
    return () => window.removeEventListener("keydown", handleShortcut, true);
  }, [runCode]);

  const updateCode = useCallback(
    (nextCode) => {
      writeStorage(STORAGE_KEYS.code(language), nextCode);
      setDrafts((current) => ({ ...current, [language]: nextCode }));
    },
    [language],
  );

  const changeLanguage = useCallback(
    (nextLanguage) => {
      if (!isSupportedLanguage(nextLanguage) || nextLanguage === language) return;
      setLanguage(nextLanguage);
      setRunState(EMPTY_RUN_STATE);
    },
    [language],
  );

  const clearAll = useCallback(() => {
    cancelActiveRun();
    writeStorage(STORAGE_KEYS.code(language), "");
    setDrafts((current) => ({ ...current, [language]: "" }));
    setRunState(EMPTY_RUN_STATE);
    if (language === "html") setPreviewDocument("");
    showToast("Editor and output cleared");
  }, [cancelActiveRun, language, showToast]);

  const resetCode = useCallback(() => {
    cancelActiveRun();
    writeStorage(STORAGE_KEYS.code(language), selectedLanguage.starter);
    setDrafts((current) => ({ ...current, [language]: selectedLanguage.starter }));
    setRunState(EMPTY_RUN_STATE);
    if (language === "html") setPreviewDocument("");
    showToast(`${selectedLanguage.label} starter restored`);
  }, [cancelActiveRun, language, selectedLanguage, showToast]);

  const copyCode = useCallback(async () => {
    try {
      const copied = await copyText(code);
      showToast(copied ? "Code copied to clipboard" : "There is no code to copy", copied ? "success" : "info");
    } catch {
      showToast("Clipboard access was blocked by the browser", "info");
    }
  }, [code, showToast]);

  const copyOutput = useCallback(
    async (value) => {
      try {
        const copied = await copyText(value);
        showToast(copied ? "Output copied to clipboard" : "There is no output to copy", copied ? "success" : "info");
      } catch {
        showToast("Clipboard access was blocked by the browser", "info");
      }
    },
    [showToast],
  );

  const downloadCode = useCallback(() => {
    if (!code) {
      showToast("There is no code to download", "info");
      return;
    }
    downloadText(code, `codex-main.${selectedLanguage.extension}`);
    showToast(`Downloaded codex-main.${selectedLanguage.extension}`);
  }, [code, selectedLanguage.extension, showToast]);

  const editor = useMemo(
    () => (
      <CodeEditor
        code={code}
        executionTimeMs={runState.executionTimeMs}
        extension={selectedLanguage.extension}
        isFullscreen={isFullscreen}
        language={selectedLanguage.monacoLanguage}
        languageLabel={selectedLanguage.label}
        onChange={updateCode}
        onCopy={copyCode}
        onDownload={downloadCode}
        onFullscreenToggle={() => setIsFullscreen((current) => !current)}
        onReset={resetCode}
        status={runState.status}
        theme={theme}
      />
    ),
    [
      code,
      copyCode,
      downloadCode,
      isFullscreen,
      resetCode,
      runState.executionTimeMs,
      runState.status,
      selectedLanguage,
      theme,
      updateCode,
    ],
  );

  const results = (
    <div className={`results-stack ${language === "html" ? "results-stack-with-preview" : ""}`}>
      {language === "html" ? <PreviewPanel document={previewDocument} /> : null}
      <OutputConsole
        onClear={() => setRunState(EMPTY_RUN_STATE)}
        onCopy={copyOutput}
        runState={runState}
      />
    </div>
  );

  return (
    <div className="app-shell">
      <Header
        isRunning={isRunning}
        language={language}
        onClear={clearAll}
        onLanguageChange={changeLanguage}
        onRun={() => void runCode()}
        onThemeToggle={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
        theme={theme}
      />

      <main className="app-main">
        <Workspace editor={editor} results={results} />
      </main>

      <Toast message={toast?.message} type={toast?.type} />
    </div>
  );
}
