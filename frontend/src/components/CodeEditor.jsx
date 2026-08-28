import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import ActionButton from "./ActionButton";
import Icon from "./Icon";
import StatusBar from "./StatusBar";
import { defineCodeXEditorThemes } from "../theme/monacoThemes";

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
          beforeMount={defineCodeXEditorThemes}
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
