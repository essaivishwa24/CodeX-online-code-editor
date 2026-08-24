import { LANGUAGE_OPTIONS } from "../constants/languages";
import Icon from "./Icon";

export default function Header({
  language,
  onLanguageChange,
  onRun,
  onClear,
  isRunning,
  theme,
  onThemeToggle,
}) {
  const isDark = theme === "dark";

  return (
    <header className="app-header">
      <div className="flex min-w-0 items-center gap-3">
        <div className="brand-mark" aria-hidden="true">
          <Icon name="code" size={22} strokeWidth={2.2} />
        </div>
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold tracking-tight text-[var(--text-strong)]">CodeX</span>
            <span className="hidden text-xs text-[var(--text-muted)] sm:inline">Online Code Editor</span>
          </div>
          <p className="mt-0.5 hidden text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--text-faint)] md:block">
            Build · Run · Learn
          </p>
        </div>
      </div>

      <div className="header-actions">
        <label className="relative min-w-[132px] sm:min-w-[154px]">
          <span className="sr-only">Programming language</span>
          <select
            aria-label="Programming language"
            className="language-select"
            disabled={isRunning}
            onChange={(event) => onLanguageChange(event.target.value)}
            value={language}
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <Icon
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            name="chevron"
            size={16}
          />
        </label>

        <button
          aria-busy={isRunning}
          className="run-button"
          disabled={isRunning}
          onClick={onRun}
          title="Run code (Ctrl/⌘ + Enter)"
          type="button"
        >
          {isRunning ? <span className="spinner" aria-hidden="true" /> : <Icon name="play" size={16} />}
          <span>{isRunning ? "Running…" : "Run"}</span>
          <kbd className="shortcut-key">Ctrl ↵</kbd>
        </button>

        <button className="header-button" onClick={onClear} title="Clear editor and output" type="button">
          <Icon name="trash" size={16} />
          <span className="hidden sm:inline">Clear</span>
        </button>

        <button
          aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
          aria-pressed={!isDark}
          className="icon-button h-10 w-10 shrink-0"
          onClick={onThemeToggle}
          title={`Switch to ${isDark ? "light" : "dark"} theme`}
          type="button"
        >
          <Icon name={isDark ? "sun" : "moon"} size={18} />
        </button>
      </div>
    </header>
  );
}
