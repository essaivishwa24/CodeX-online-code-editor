import Icon from "./Icon";

const EMPTY_DOCUMENT = "<!doctype html><html><body></body></html>";

export default function PreviewPanel({ document: previewDocument }) {
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
        <span className="safe-badge">Scripts blocked</span>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-white">
        <iframe
          className="h-full min-h-[210px] w-full border-0 bg-white"
          referrerPolicy="no-referrer"
          sandbox=""
          srcDoc={previewDocument || EMPTY_DOCUMENT}
          title="CodeX HTML preview"
        />
        {!hasPreview ? (
          <div className="pointer-events-none absolute inset-0 grid place-items-center bg-white">
            <div className="max-w-[260px] px-5 text-center">
              <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-slate-500">
                <Icon name="eye" size={18} />
              </div>
              <p className="text-sm font-semibold text-slate-700">Preview is ready</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">Press Run to render your current HTML and CSS.</p>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
