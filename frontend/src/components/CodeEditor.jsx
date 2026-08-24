import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import ActionButton from "./ActionButton";
import Icon from "./Icon";
import StatusBar from "./StatusBar";

function EditorLoading() {
  return (
    <div className="flex h-full min-h-[280px] items-center justify-center bg-[var(--editor-bg)]" role="status">
      <div className="flex items-center gap-3 text-sm text-[var(--text-muted)]">
        <span className="spinner" aria-hidden="true" />
        Loading editor…
      </div>
    </div>
  );
}

function defineThemes(monaco) {
  monaco.editor.defineTheme("codex-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#101218",
      "editor.foreground": "#d6d9e2",
      "editorLineNumber.foreground": "#565b69",
      "editorLineNumber.activeForeground": "#a7afc2",
      "editor.selectionBackground": "#4f64cb55",
      "editor.inactiveSelectionBackground": "#4f64cb2e",
      "editor.lineHighlightBackground": "#171a22",
      "editorCursor.foreground": "#91a1ff",
      "editorIndentGuide.background1": "#242833",
      "editorIndentGuide.activeBackground1": "#42495b",
      "editorWidget.background": "#181b23",
      "editorSuggestWidget.background": "#181b23",
      "editorSuggestWidget.border": "#2b303c",
      "editorHoverWidget.background": "#181b23",
      "editorHoverWidget.border": "#2b303c",
    },
  });

  monaco.editor.defineTheme("codex-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#ffffff",
      "editor.foreground": "#202431",
      "editorLineNumber.foreground": "#a4a9b5",
      "editorLineNumber.activeForeground": "#555c6d",
      "editor.selectionBackground": "#7487f733",
      "editor.lineHighlightBackground": "#f7f8fc",
      "editorCursor.foreground": "#5365d5",
      "editorIndentGuide.background1": "#e6e8ef",
      "editorIndentGuide.activeBackground1": "#c5cad8",
    },
  });
}

export default function CodeEditor({
  code,
  onChange,
  language,
  languageLabel,
  extension,
  theme,
  status,
  executionTimeMs,
  onCopy,
  onDownload,
  onReset,
  isFullscreen,
  onFullscreenToggle,
}) {
  const editorRef = useRef(null);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => editorRef.current?.layout());
    return () => window.cancelAnimationFrame(frameId);
  }, [isFullscreen]);

  return (
    <section
      aria-label="Code editor"
      className={`panel editor-panel ${isFullscreen ? "editor-fullscreen" : ""}`}
    >
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="panel-icon">
            <Icon name="code" size={15} />
          </div>
          <div className="min-w-0">
            <h2 className="panel-title">Editor</h2>
            <p className="truncate text-[11px] text-[var(--text-faint)]">main.{extension}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <ActionButton icon="copy" label="Copy code" onClick={onCopy} />
          <ActionButton icon="download" label={`Download main.${extension}`} onClick={onDownload} />
          <ActionButton icon="reset" label="Reset to starter code" onClick={onReset} />
          <div className="mx-1 h-5 w-px bg-[var(--border)]" aria-hidden="true" />
          <ActionButton
            active={isFullscreen}
            icon={isFullscreen ? "minimize" : "maximize"}
            label={isFullscreen ? "Exit full screen" : "Open editor full screen"}
            onClick={onFullscreenToggle}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 bg-[var(--editor-bg)]">
        <Editor
          beforeMount={defineThemes}
          height="100%"
          language={language}
          loading={<EditorLoading />}
          onChange={(value) => onChange(value ?? "")}
          onMount={(editor) => {
            editorRef.current = editor;
          }}
          options={{
            accessibilitySupport: "auto",
            automaticLayout: true,
            bracketPairColorization: { enabled: true },
            cursorBlinking: "smooth",
            cursorSmoothCaretAnimation: "on",
            fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
            fontLigatures: true,
            fontSize: 14,
            formatOnPaste: true,
            guides: { bracketPairs: true, indentation: true },
            lineHeight: 22,
            lineNumbers: "on",
            matchBrackets: "always",
            minimap: { enabled: false },
            padding: { top: 14, bottom: 14 },
            roundedSelection: true,
            scrollBeyondLastLine: false,
            smoothScrolling: true,
            suggestOnTriggerCharacters: true,
            tabSize: language === "python" ? 4 : 2,
            insertSpaces: true,
            wordWrap: "off",
          }}
          theme={theme === "dark" ? "codex-dark" : "codex-light"}
          value={code}
        />
      </div>

      <StatusBar
        code={code}
        executionTimeMs={executionTimeMs}
        languageLabel={languageLabel}
        status={status}
      />
    </section>
  );
}
