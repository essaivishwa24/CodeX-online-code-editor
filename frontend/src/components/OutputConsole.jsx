import ActionButton from "./ActionButton";
import Icon from "./Icon";

const STATUS_LABELS = {
  idle: "Ready",
  running: "Running",
  success: "Success",
  error: "Error",
};

function displayContent(runState) {
  if (runState.status === "running") {
    return "> Starting execution…\n> Waiting for the runner";
  }

  if (runState.status === "error") {
    return runState.error || "An unknown execution error occurred.";
  }

  if (runState.status === "success") {
    return runState.output || "Program finished successfully with no output.";
  }

  return "Run your code to see the result here.\n\nTip: press Ctrl/⌘ + Enter from anywhere in the editor.";
}

export default function OutputConsole({ runState, onCopy, onClear }) {
  const display = displayContent(runState);
  const copyable = runState.error || runState.output;

  return (
    <section aria-label="Program output" className="panel output-panel">
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="panel-icon">
            <Icon name="terminal" size={15} />
          </div>
          <div>
            <h2 className="panel-title">Output</h2>
            <p className="text-[11px] text-[var(--text-faint)]">Terminal</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <span className={`output-status output-status-${runState.status}`}>
            <span className={`status-dot status-${runState.status}`} aria-hidden="true" />
            {STATUS_LABELS[runState.status]}
          </span>
          <ActionButton disabled={!copyable} icon="copy" label="Copy output" onClick={() => onCopy(copyable)} />
          <ActionButton
            disabled={runState.status === "idle" || runState.status === "running"}
            icon="close"
            label="Clear output"
            onClick={onClear}
          />
        </div>
      </div>

      <div className="terminal-body">
        <div className="terminal-chrome" aria-hidden="true">
          <span className="terminal-dot terminal-dot-error" />
          <span className="terminal-dot terminal-dot-warning" />
          <span className="terminal-dot terminal-dot-success" />
          <span className="terminal-session-label">
            codex — session
          </span>
        </div>
        <pre
          aria-live={runState.status === "error" ? "assertive" : "polite"}
          className={`terminal-output terminal-output-${runState.status}`}
          role={runState.status === "error" ? "alert" : "status"}
        >
          {display}
        </pre>
      </div>
    </section>
  );
}
