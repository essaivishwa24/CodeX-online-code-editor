import { useCallback, useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import PreviewPanel from "./components/PreviewPanel";
import SQLResultTable from "./components/SQLResultTable";
import { filenameForLanguage, languageForFilename, LANGUAGES, LANGUAGE_OPTIONS, languageOptionLabel, STORAGE_KEYS } from "./constants/languages";
import {
  ApiError,
  createFile,
  createProject,
  deleteProject,
  executeCode,
  getCurrentUser,
  getProject,
  getRuntimeStatus,
  getToken,
  listProjects,
  login,
  logout,
  register,
  resetSqlPlayground,
  saveFile,
  setToken,
  updateProject,
} from "./services/api";
import { copyText, createProjectPreview } from "./utils/browser";

const OUTPUT_STATUS_LABELS = {
  idle: "Ready",
  running: "Running",
  success: "Success",
  error: "Error",
};

function sqlWorkspaceId(projectId, fileId) {
  if (!projectId) return "default";
  const storageKey = STORAGE_KEYS.sqlWorkspace(projectId, fileId);
  let workspaceId = localStorage.getItem(storageKey);
  if (!workspaceId) {
    workspaceId = globalThis.crypto?.randomUUID?.()
      || `project-${projectId}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(storageKey, workspaceId);
  }
  return workspaceId;
}

function formatRunResult(result, language) {
  const label = LANGUAGES[language]?.label || language;
  const status = result.status === "compilation_error" ? "Compilation failed"
    : result.status === "runtime_error" ? "Runtime error"
      : result.status === "timeout" ? "Time limit exceeded"
        : result.success ? "Run completed" : "Error";
  const icon = result.success ? "✓" : result.status === "timeout" ? "◷" : "✕";
  const elapsed = result.executionTimeMs == null ? "—" : `${(result.executionTimeMs / 1000).toFixed(2)}s`;
  const contentSections = [];
  if (result.status === "timeout") {
    contentSections.push("Your program exceeded the maximum execution time.");
  } else {
    if (result.stdout) contentSections.push(`Output\n${result.stdout}`);
    if (result.stderr) contentSections.push(`Errors\n${result.stderr}`);
    if (!contentSections.length) contentSections.push(result.success
      ? "Program finished successfully with no output."
      : "The execution failed.");
  }
  const details = [
    `Language: ${label}`,
    `Status: ${status}`,
    `Execution time: ${elapsed}`,
    ...(result.exitCode == null ? [] : [`Exit code: ${result.exitCode}`]),
  ];
  return `${icon} ${status}    ${elapsed}\n\n${contentSections.join("\n\n")}\n\nExecution details\n${details.join("\n")}`;
}

function friendlyAuthError(error) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Invalid email or password.";
    if (error.status === 403) return "This account is currently disabled.";
    if (error.status === 404 || error.code === "NETWORK_ERROR") return "Unable to contact the CodeX API.";
    if (error.status >= 500) return "Unable to sign in right now. Please try again.";
  }
  return error?.message || "Unable to sign in right now. Please try again.";
}

function Auth({ initialMessage = "", onAuthenticated }) {
  const [signup, setSignup] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", confirm_password: "" });
  const [error, setError] = useState(initialMessage);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    if (error) setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    if (isSubmitting) return;
    setError("");
    setIsSubmitting(true);
    try {
      const credentials = signup
        ? { ...form, email: form.email.trim().toLowerCase() }
        : { email: form.email.trim().toLowerCase(), password: form.password };
      const result = signup ? await register(credentials) : await login(credentials);
      await onAuthenticated(result);
    } catch (requestError) {
      setError(friendlyAuthError(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="panel auth-card w-full max-w-md space-y-4 p-8" onSubmit={submit}>
        <div className="flex min-w-0 items-center gap-3">
          <div className="brand-mark">⌘</div>
          <div className="auth-brand-copy min-w-0">
            <h1 className="text-2xl font-bold text-[var(--text-strong)]">CodeX</h1>
            <p className="auth-tagline break-words text-sm leading-5 text-[var(--text-muted)]">Your focused online coding workspace</p>
          </div>
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-strong)]">
          {signup ? "Create your account" : "Welcome back"}
        </h2>
        {signup && (
          <input
            autoComplete="username"
            className="form-input w-full"
            disabled={isSubmitting}
            maxLength={40}
            minLength={3}
            onChange={(event) => updateField("username", event.target.value)}
            pattern="[A-Za-z0-9_-]+"
            placeholder="Username"
            required
            value={form.username}
          />
        )}
        <input
          autoComplete="email"
          className="form-input w-full"
          disabled={isSubmitting}
          onChange={(event) => updateField("email", event.target.value)}
          placeholder="Email"
          required
          type="email"
          value={form.email}
        />
        <input
          autoComplete={signup ? "new-password" : "current-password"}
          className="form-input w-full"
          disabled={isSubmitting}
          minLength={8}
          onChange={(event) => updateField("password", event.target.value)}
          placeholder="Password (8+ characters)"
          required
          type="password"
          value={form.password}
        />
        {signup && (
          <input
            autoComplete="new-password"
            className="form-input w-full"
            disabled={isSubmitting}
            minLength={8}
            onChange={(event) => updateField("confirm_password", event.target.value)}
            placeholder="Confirm password"
            required
            type="password"
            value={form.confirm_password}
          />
        )}
        {error && <p className="text-sm text-[var(--error)]" role="alert">{error}</p>}
        <button className="primary-button w-full" disabled={isSubmitting} type="submit">
          {isSubmitting ? (signup ? "Creating account…" : "Signing in…") : (signup ? "Sign up" : "Log in")}
        </button>
        <button
          className="text-link"
          disabled={isSubmitting}
          onClick={() => { setSignup((current) => !current); setError(""); }}
          type="button"
        >
          {signup ? "Already have an account? Log in" : "Need an account? Sign up"}
        </button>
      </form>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null);
  const [file, setFile] = useState(null);
  const [code, setCode] = useState("");
  const [output, setOutput] = useState("");
  const [outputStatus, setOutputStatus] = useState("idle");
  const [sqlResult, setSqlResult] = useState(null);
  const [runtimeStatuses, setRuntimeStatuses] = useState({});
  const [stdin, setStdin] = useState("");
  const [previewDocument, setPreviewDocument] = useState("");
  const [previewAllowsScripts, setPreviewAllowsScripts] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Copy output");
  const [saving, setSaving] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem("codex:theme") || "dark");
  const [authChecked, setAuthChecked] = useState(false);
  const [authMessage, setAuthMessage] = useState("");
  const [restoreError, setRestoreError] = useState("");

  const refreshRuntimeStatus = useCallback(async () => {
    try {
      const result = await getRuntimeStatus();
      setRuntimeStatuses(result.runtimes || {});
    } catch {
      // Runtime discovery is supplemental; execution still returns the full error.
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("codex:theme", theme);
  }, [theme]);

  useEffect(() => {
    if (user) void refreshRuntimeStatus();
  }, [refreshRuntimeStatus, user]);

  const restoreSession = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setAuthChecked(true);
      return;
    }

    setAuthChecked(false);
    setRestoreError("");
    try {
      const restoredUser = await getCurrentUser();
      setUser(restoredUser);
      setProjects(await listProjects());
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setToken(null);
        setUser(null);
        setAuthMessage("Your session has expired. Please sign in again.");
      } else {
        setRestoreError("Unable to contact the CodeX API.");
      }
    } finally {
      setAuthChecked(true);
    }
  }, []);

  useEffect(() => { void restoreSession(); }, [restoreSession]);

  const handleAuthenticated = async (result) => {
    setToken(result.access_token);
    try {
      const verifiedUser = await getCurrentUser();
      const savedProjects = await listProjects();
      setUser(verifiedUser);
      setProjects(savedProjects);
      setAuthMessage("");
      setRestoreError("");
    } catch (error) {
      setToken(null);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Local logout must still complete if the server is unavailable.
    } finally {
      setToken(null);
      setUser(null);
      setProjects([]);
      setProject(null);
      setFile(null);
      setCode("");
      setOutput("");
      setOutputStatus("idle");
      setSqlResult(null);
      setRuntimeStatuses({});
      setStdin("");
      setPreviewDocument("");
      setAuthMessage("");
    }
  };

  if (!authChecked) {
    return <div className="grid min-h-screen place-items-center">Loading CodeX…</div>;
  }

  if (restoreError && getToken() && !user) {
    return (
      <div className="auth-page">
        <div className="panel auth-card max-w-md space-y-4 p-8 text-center">
          <h1 className="text-xl font-semibold text-[var(--text-strong)]">CodeX is unavailable</h1>
          <p className="text-sm text-[var(--text-muted)]">{restoreError}</p>
          <button className="primary-button w-full" onClick={() => void restoreSession()} type="button">Try again</button>
          <button className="header-button w-full" onClick={() => void handleLogout()} type="button">Sign out</button>
        </div>
      </div>
    );
  }

  if (!user) return <Auth initialMessage={authMessage} onAuthenticated={handleAuthenticated} />;

  const open = async (selectedProject) => {
    const fullProject = await getProject(selectedProject.id);
    const normalizedProject = {
      ...fullProject,
      files: fullProject.files.map((projectFile) => ({
        ...projectFile,
        language: languageForFilename(projectFile.filename, projectFile.language),
      })),
    };
    setProject(normalizedProject);
    setFile(normalizedProject.files[0]);
    setCode(normalizedProject.files[0]?.content || "");
    setOutput("");
    setOutputStatus("idle");
    setSqlResult(null);
    setPreviewDocument("");
  };

  const save = async () => {
    if (!project || !file) return;
    setSaving(true);
    try {
      await saveFile(project.id, file.id, {
        content: code,
        filename: file.filename,
        language: file.language,
      });
      setFile({ ...file, content: code });
      setProject((current) => ({
        ...current,
        files: current.files.map((projectFile) => projectFile.id === file.id
          ? { ...file, content: code }
          : projectFile),
      }));
      setProjects(await listProjects());
    } finally {
      setSaving(false);
    }
  };

  const create = async () => {
    const created = await createProject({
      name: `untitled-${projects.length + 1}`,
      primary_language: "python",
      template: "basic",
    });
    setProjects([created, ...projects]);
    await open(created);
  };

  const run = async () => {
    setOutput("Running…");
    setOutputStatus("running");
    setSqlResult(null);
    const previewFiles = project.files.map((projectFile) => projectFile.id === file.id
      ? { ...projectFile, ...file, content: code }
      : projectFile);
    if (file.language === "html" || file.language === "css") {
      const preview = createProjectPreview(previewFiles);
      if (!preview) {
        setPreviewDocument("");
        setPreviewAllowsScripts(false);
        setOutput("CSS is a styling language. Add or open an HTML file to preview it.");
        setOutputStatus("idle");
        return;
      }
      setPreviewDocument(preview);
      setPreviewAllowsScripts(previewFiles.some((projectFile) => /\.(js|jsx)$/i.test(projectFile.filename)));
      setOutput(`✓ Preview refreshed    —\n\nRendered in the sandboxed preview.`);
      setOutputStatus("success");
      return;
    }
    setPreviewDocument("");
    setPreviewAllowsScripts(false);
    try {
      const result = await executeCode({
        language: file.language,
        code,
        stdin,
        workspaceId: file.language === "sql" ? sqlWorkspaceId(project.id, file.id) : "default",
      });
      setSqlResult(file.language === "sql" && result.success ? result : null);
      setOutput(file.language === "sql" && result.success ? "" : formatRunResult(result, file.language));
      setOutputStatus(result.success ? "success" : "error");
    } catch (error) {
      setOutput(formatRunResult({ success: false, status: "unavailable", stderr: error.message }, file.language));
      setOutputStatus("error");
      if (file.language === "java" || file.language === "c") void refreshRuntimeStatus();
    }
  };

  const resetSql = async () => {
    if (!project || file?.language !== "sql") return;
    if (!window.confirm("Reset this SQL playground? All playground tables and rows for this project will be deleted.")) return;
    setOutputStatus("running");
    setSqlResult(null);
    setOutput("Resetting SQL playground…");
    try {
      const result = await resetSqlPlayground(sqlWorkspaceId(project.id, file.id));
      setOutput(result.message);
      setOutputStatus("success");
    } catch (error) {
      setOutput(`SQL reset failed:\n${error.message}`);
      setOutputStatus("error");
    }
  };

  const createNewFile = async () => {
    if (!project || !file) return;
    const requestedName = window.prompt("Filename", filenameForLanguage("", file.language));
    if (requestedName === null) return;
    const filename = requestedName.trim();
    if (!filename || filename === "." || filename === ".." || /[\\/]/.test(filename) || !/^[A-Za-z0-9._ -]+$/.test(filename)) {
      setOutput("Invalid filename. Use letters, numbers, dots, underscores, spaces, and hyphens only.");
      setOutputStatus("error");
      return;
    }
    const createdFile = await createFile(project.id, {
      filename,
      language: file.language,
      content: LANGUAGES[file.language]?.starter || "",
    });
    const fullProject = await getProject(project.id);
    setProject(fullProject);
    setFile(createdFile);
    setCode(createdFile.content);
    setOutput("");
    setOutputStatus("idle");
    setSqlResult(null);
    setPreviewDocument("");
  };

  const clearOutput = () => {
    setOutput("");
    setOutputStatus("idle");
    setSqlResult(null);
    setCopyLabel("Copy output");
  };

  const copyOutput = async () => {
    if (!output) return;
    const copied = await copyText(output);
    if (copied) {
      setCopyLabel("Copied");
      window.setTimeout(() => setCopyLabel("Copy output"), 1400);
    }
  };

  const changeLanguage = (nextLanguage) => {
    const config = LANGUAGES[nextLanguage];
    if (!file || !config || nextLanguage === file.language) return;
    setFile({
      ...file,
      language: nextLanguage,
      filename: filenameForLanguage(file.filename, nextLanguage),
    });
    setCode(config.starter);
    setOutput("");
    setOutputStatus("idle");
    setSqlResult(null);
    setPreviewDocument("");
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="flex min-w-0 items-center gap-3">
          <div className="brand-mark">⌘</div>
          <div className="min-w-0">
            <b className="text-lg text-[var(--text-strong)]">CodeX</b>
            <span className="ml-2 text-xs text-[var(--text-muted)]">Online coding workspace</span>
          </div>
        </div>
        <div className="header-actions">
          <button className="primary-button" onClick={() => void create()} type="button">＋ New project</button>
          <button aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} className="icon-button h-10 w-10" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} type="button">{theme === "dark" ? "☼" : "☾"}</button>
          <button className="header-button" onClick={() => void handleLogout()} type="button">Log out</button>
        </div>
      </header>
      <main className="app-main">
        {!project ? (
          <section className="dashboard mx-auto max-w-6xl space-y-6">
            <div className="dashboard-heading flex items-end justify-between">
              <div>
                <p className="text-sm text-[var(--brand)]">Workspace</p>
                <h1 className="text-3xl font-bold text-[var(--text-strong)]">Good to see you, {user.username}.</h1>
                <p className="text-[var(--text-muted)]">Pick up where you left off.</p>
              </div>
              <button className="primary-button" onClick={() => void create()} type="button">Create project</button>
            </div>
            <input className="form-input search-input w-full" placeholder="Search projects…" onChange={(event) => setProjects((current) => current.filter((item) => item.name.toLowerCase().includes(event.target.value.toLowerCase())))} />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((item) => (
                <article className="panel project-card p-5" key={item.id}>
                  <div className="flex justify-between">
                    <span className="language-badge">{item.primary_language}</span>
                    <button aria-label={item.is_favorite ? "Remove from favorites" : "Add to favorites"} className="favorite-button" onClick={() => updateProject(item.id, { is_favorite: !item.is_favorite }).then(() => listProjects().then(setProjects))} type="button">{item.is_favorite ? "★" : "☆"}</button>
                  </div>
                  <h2 className="mt-5 font-semibold text-[var(--text-strong)]">{item.name}</h2>
                  <p className="mt-1 text-sm text-[var(--text-muted)]">{item.files?.length || 0} files · {new Date(item.updated_at).toLocaleDateString()}</p>
                  <div className="mt-5 flex gap-2">
                    <button className="header-button" onClick={() => void open(item)} type="button">Open</button>
                    <button className="danger-button" onClick={() => deleteProject(item.id).then(() => listProjects().then(setProjects))} type="button">Delete</button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : (
          <section className="project-workspace">
            <aside className="panel file-explorer p-3">
              <div className="mb-3 flex justify-between"><b className="text-[var(--text-strong)]">{project.name}</b><button className="text-button" onClick={() => setProject(null)} type="button">Back</button></div>
              {project.files.map((projectFile) => (
                <button className={`file-row ${file?.id === projectFile.id ? "file-row-active" : ""}`} key={projectFile.id} onClick={() => { setFile({ ...projectFile, language: languageForFilename(projectFile.filename, projectFile.language) }); setCode(projectFile.content); setOutput(""); setOutputStatus("idle"); setSqlResult(null); setPreviewDocument(""); }} type="button">{projectFile.filename}</button>
              ))}
              <button className="text-link mt-3" onClick={() => void createNewFile()} type="button">＋ New file</button>
            </aside>
            <section className="panel editor-panel">
              <div className="panel-header editor-panel-header">
                <b className="editor-file-name text-[var(--text-strong)]">{file?.filename || "No file"}</b>
                <div className="editor-actions flex gap-2">
                  <select aria-label="Programming language" className="language-select" onChange={(event) => changeLanguage(event.target.value)} onFocus={() => void refreshRuntimeStatus()} value={file?.language || "python"}>
                    {LANGUAGE_OPTIONS.map((language) => <option key={language.id} value={language.id}>{languageOptionLabel(language, runtimeStatuses)}</option>)}
                  </select>
                  <button className="run-button" onClick={() => void run()} type="button">▶ Run</button>
                  <button className="header-button" onClick={() => void save()} type="button">{saving ? "Saving…" : "Save"}</button>
                </div>
              </div>
              <div className="min-h-0 flex-1"><Editor height="100%" language={LANGUAGES[file?.language]?.monacoLanguage || "plaintext"} onChange={(value) => setCode(value ?? "")} options={{ automaticLayout: true, lineHeight: 22, minimap: { enabled: false }, padding: { top: 10, bottom: 10 }, scrollBeyondLastLine: false, fontSize: 14 }} path={`${project.id}/${file?.filename || "untitled"}`} theme={theme === "dark" ? "codex-dark" : "codex-light"} value={code} /></div>
              <div className={`save-status ${saving ? "save-status-pending" : "save-status-saved"}`}>{saving ? "Saving…" : "Saved to SQL"}</div>
            </section>
            <div className={`results-stack ${(file?.language === "html" || file?.language === "css") ? "results-stack-with-preview" : ""}`}>
              {(file?.language === "html" || file?.language === "css") && <PreviewPanel allowScripts={previewAllowsScripts} document={previewDocument} />}
              <section className="panel output-panel">
                <div className="panel-header">
                  <b className="text-[var(--text-strong)]">{file?.language === "sql" ? "SQL results" : "Output"}</b>
                  <div className="flex items-center gap-2">
                    <span className={`output-status output-status-${outputStatus}`}>
                      <span className={`status-dot status-${outputStatus}`} aria-hidden="true" />
                      {OUTPUT_STATUS_LABELS[outputStatus]}
                    </span>
                    {file?.language === "sql" && <button className="text-button" disabled={outputStatus === "running"} onClick={() => void resetSql()} type="button">Reset DB</button>}
                    <button className="text-button" disabled={!output} onClick={() => void copyOutput()} type="button">{copyLabel}</button>
                    <button className="text-button" disabled={outputStatus === "running"} onClick={clearOutput} type="button">Clear</button>
                  </div>
                </div>
                {file?.language !== "sql" && <label className="border-b border-[var(--border)] p-3 text-xs font-semibold text-[var(--text-muted)]">
                  Program Input
                  <textarea aria-label="Program Input" className="stdin-input mt-2 block h-16 w-full resize-y font-mono text-xs" onChange={(event) => setStdin(event.target.value)} placeholder="Optional input, one value per line" value={stdin} />
                </label>}
                {file?.language === "sql" && sqlResult
                  ? <SQLResultTable result={sqlResult} />
                  : <pre className={`terminal-output terminal-output-${outputStatus}`}>{output || "Run your code to see output here."}</pre>}
              </section>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
