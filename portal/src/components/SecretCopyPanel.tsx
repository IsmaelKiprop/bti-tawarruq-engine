import { useEffect, useState } from "react";
import { IconCheck, IconCopy } from "./icons";

export type SecretCopyItem = {
  id: string;
  label: string;
  value?: string;
  prefix?: string;
};

function maskSecret(item: SecretCopyItem): string {
  const prefix = item.prefix?.trim();
  if (prefix) return `${prefix}${"•".repeat(12)}`;
  return "••••••••••••••••";
}

export function SecretCopyPanel({
  title,
  note,
  secrets,
  institutionId,
  onReveal,
}: {
  title: string;
  note?: string;
  secrets: SecretCopyItem[];
  institutionId?: string;
  onReveal?: (password: string) => Promise<SecretCopyItem[]>;
}) {
  const [unlocked, setUnlocked] = useState(() => secrets.some((item) => item.value));
  const [shown, setShown] = useState<Record<string, string>>(() =>
    Object.fromEntries(secrets.filter((item) => item.value).map((item) => [item.id, item.value || ""])),
  );
  const [copied, setCopied] = useState("");
  const [password, setPassword] = useState("");
  const [askPassword, setAskPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const incoming = Object.fromEntries(secrets.filter((item) => item.value).map((item) => [item.id, item.value || ""]));
    if (Object.keys(incoming).length && unlocked) {
      setShown((current) => ({ ...current, ...incoming }));
    }
  }, [secrets, unlocked]);

  const rows = secrets;
  if (!rows.length) return null;

  function hide() {
    setUnlocked(false);
    setShown({});
    setAskPassword(false);
    setPassword("");
    setError("");
  }

  async function reveal() {
    if (!onReveal) {
      setUnlocked(true);
      setShown(Object.fromEntries(secrets.filter((item) => item.value).map((item) => [item.id, item.value || ""])));
      setAskPassword(false);
      return;
    }
    if (!password.trim()) {
      setError("Enter your password to show the key.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const next = await onReveal(password);
      setShown(Object.fromEntries(next.filter((item) => item.value).map((item) => [item.id, item.value || ""])));
      setUnlocked(true);
      setAskPassword(false);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reveal the key");
    } finally {
      setBusy(false);
    }
  }

  async function copy(id: string, text: string) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      window.setTimeout(() => setCopied((current) => (current === id ? "" : current)), 1800);
    } catch {
      /* user can still select the field */
    }
  }

  async function copyAll() {
    const text = rows
      .map((item) => `${item.label}: ${shown[item.id] || ""}`)
      .filter((line) => !line.endsWith(": "))
      .join("\n");
    await copy("all", text);
  }

  return (
    <section className="secret-copy-panel" aria-label={title}>
      <header className="secret-copy-head">
        <div>
          <h3>{title}</h3>
          {note ? <p className="muted m-0">{note}</p> : null}
        </div>
        <div className="secret-copy-head-actions">
          {unlocked && rows.length > 1 ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void copyAll()}>
              {copied === "all" ? <IconCheck size={14} /> : <IconCopy size={14} />}
              {copied === "all" ? "Copied both" : "Copy both"}
            </button>
          ) : null}
          {unlocked ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={hide}>
              Hide
            </button>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setAskPassword(true)}>
              Show
            </button>
          )}
        </div>
      </header>

      {askPassword && !unlocked ? (
        <div className="secret-copy-unlock">
          <label>
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void reveal();
              }}
            />
          </label>
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void reveal()}>
            {busy ? "Checking…" : institutionId ? "Show keys" : "Show"}
          </button>
        </div>
      ) : null}
      {error ? <p className="secret-copy-error">{error}</p> : null}

      <div className="secret-copy-list">
        {rows.map((item) => {
          const value = unlocked ? shown[item.id] || item.value || "" : "";
          const display = unlocked && value ? value : maskSecret(item);
          return (
            <label key={item.id} className="secret-copy-row">
              <span>{item.label}</span>
              <div className="secret-copy-field">
                <input
                  className="secret-copy-value"
                  readOnly
                  value={display}
                  onFocus={(event) => unlocked && event.currentTarget.select()}
                  aria-label={item.label}
                />
                {unlocked && value ? (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => void copy(item.id, value)}>
                    {copied === item.id ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    {copied === item.id ? "Copied" : "Copy"}
                  </button>
                ) : (
                  <button type="button" className="btn btn-secondary btn-sm" disabled>
                    Hidden
                  </button>
                )}
              </div>
            </label>
          );
        })}
      </div>
    </section>
  );
}
