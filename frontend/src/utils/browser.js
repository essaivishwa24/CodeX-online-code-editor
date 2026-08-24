export async function copyText(text) {
  if (!text) {
    return false;
  }

  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  return copied;
}

export function downloadText(content, filename) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

const PREVIEW_POLICY = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "img-src data: blob: https:",
  "font-src data: https:",
  "connect-src 'none'",
  "script-src 'none'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

export function createSandboxedDocument(source) {
  const securityMeta = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_POLICY}">`;

  if (/<head(?:\s[^>]*)?>/i.test(source)) {
    return source.replace(/<head(?:\s[^>]*)?>/i, (head) => `${head}${securityMeta}`);
  }

  return `<!doctype html><html><head>${securityMeta}</head><body>${source}</body></html>`;
}
