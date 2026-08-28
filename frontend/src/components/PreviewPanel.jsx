import Icon from "./Icon";

const EMPTY_DOCUMENT = "<!doctype html><html><body></body></html>";

export default function PreviewPanel({ allowScripts = false, document: previewDocument }) {
  const hasPreview = Boolean(previewDocument);

  return (
    <section aria-label="HTML preview" className="panel preview-panel">
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="panel-icon">
            <Icon name="eye" size={15} />
          </div>
          <div>
            <h2 className="panel-title">Preview</h2>
            <p className="text-[11px] text-[var(--text-faint)]">Sandboxed HTML / CSS</p>
          </div>
        </div>
        <span className="safe-badge">{allowScripts ? "Scripts sandboxed" : "Scripts blocked"}</span>
      </div>

      <div className="preview-canvas relative min-h-0 flex-1 overflow-hidden">
        <iframe
          className="preview-frame h-full min-h-[210px] w-full border-0"
          referrerPolicy="no-referrer"
          sandbox={allowScripts ? "allow-scripts" : ""}
          srcDoc={previewDocument || EMPTY_DOCUMENT}
          title="CodeX HTML preview"
        />
        {!hasPreview ? (
          <div className="preview-empty-state pointer-events-none absolute inset-0 grid place-items-center">
            <div className="max-w-[260px] px-5 text-center">
              <div className="preview-empty-icon mx-auto mb-3">
                <Icon name="eye" size={18} />
              </div>
              <p className="preview-empty-title text-sm font-semibold">Preview is ready</p>
              <p className="preview-empty-copy mt-1 text-xs leading-5">Press Run to render your current HTML and CSS.</p>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
