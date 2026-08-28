const CODEX_DARK_COLORS = {
  "editor.background": "#0d1117",
  "editor.foreground": "#c9d1d9",
  "editorGutter.background": "#0d1117",
  "editorLineNumber.foreground": "#6e7681",
  "editorLineNumber.activeForeground": "#8b949e",
  "editor.selectionBackground": "#2f81f755",
  "editor.inactiveSelectionBackground": "#2f81f72b",
  "editor.lineHighlightBackground": "#161b22",
  "editorCursor.foreground": "#2f81f7",
  "editorIndentGuide.background1": "#21262d",
  "editorIndentGuide.activeBackground1": "#484f58",
  "editorWidget.background": "#21262d",
  "editorWidget.border": "#30363d",
  "editorSuggestWidget.background": "#21262d",
  "editorSuggestWidget.border": "#30363d",
  "editorHoverWidget.background": "#21262d",
  "editorHoverWidget.border": "#30363d",
  "input.background": "#0d1117",
  "input.border": "#30363d",
  "focusBorder": "#2f81f7",
};

const CODEX_LIGHT_COLORS = {
  "editor.background": "#ffffff",
  "editor.foreground": "#24292f",
  "editorGutter.background": "#ffffff",
  "editorLineNumber.foreground": "#6e7781",
  "editorLineNumber.activeForeground": "#57606a",
  "editor.selectionBackground": "#0969da33",
  "editor.inactiveSelectionBackground": "#0969da1f",
  "editor.lineHighlightBackground": "#f6f8fa",
  "editorCursor.foreground": "#0969da",
  "editorIndentGuide.background1": "#d0d7de",
  "editorIndentGuide.activeBackground1": "#afb8c1",
  "editorWidget.background": "#ffffff",
  "editorWidget.border": "#d0d7de",
  "editorSuggestWidget.background": "#ffffff",
  "editorSuggestWidget.border": "#d0d7de",
  "editorHoverWidget.background": "#ffffff",
  "editorHoverWidget.border": "#d0d7de",
  "input.background": "#f6f8fa",
  "input.border": "#d0d7de",
  "focusBorder": "#0969da",
};

export function defineCodeXEditorThemes(monaco) {
  monaco.editor.defineTheme("codex-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: CODEX_DARK_COLORS,
  });

  monaco.editor.defineTheme("codex-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: CODEX_LIGHT_COLORS,
  });
}
