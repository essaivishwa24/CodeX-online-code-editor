const STATUS_LABELS = {
  idle: "Ready",
  running: "Running",
  success: "Completed",
  error: "Error",
};

export default function StatusBar({ languageLabel, code, status, executionTimeMs }) {
  const lines = code.length === 0 ? 1 : code.split("\n").length;
  const characters = code.length;
  const statusLabel = STATUS_LABELS[status] || STATUS_LABELS.idle;

  return (
    <footer className="status-bar">
      <div className="flex min-w-0 items-center gap-2">
        <span className={`status-dot status-${status}`} aria-hidden="true" />
        <span className="truncate font-medium text-[var(--text)]">{languageLabel}</span>
      </div>
      <div className="flex items-center gap-2.5 text-[var(--text-muted)] sm:gap-4">
        <span>Ln {lines}</span>
        <span>Ch {characters.toLocaleString()}</span>
        {executionTimeMs !== null && status === "success" ? (
          <span className="hidden sm:inline">{Math.round(executionTimeMs)} ms</span>
        ) : null}
        <span className={`font-medium status-text-${status}`}>{statusLabel}</span>
      </div>
    </footer>
  );
}
