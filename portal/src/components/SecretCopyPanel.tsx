import { useState } from "react";
import { IconCheck, IconCopy } from "./icons";

export type SecretCopyItem = {
  id: string;
  label: string;
  value: string;
};

export function SecretCopyPanel({
  title,
  note,
  secrets,
}: {
  title: string;
  note?: string;
  secrets: SecretCopyItem[];
}) {
  const rows = secrets.filter((item) => item.value);
  const [copied, setCopied] = useState("");

  if (!rows.length) return null;

  async function copy(id: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      window.setTimeout(() => setCopied((current) => (current === id ? "" : current)), 1800);
    } catch {
      /* user can still select the field */
    }
  }

  async function copyAll() {
    const text = rows.map((item) => `${item.label}: ${item.value}`).join("\n");
    await copy("all", text);
  }

  return (
    <section className="secret-copy-panel" aria-label={title}>
      <header className="secret-copy-head">
        <div>
          <h3>{title}</h3>
          {note ? <p className="muted m-0">{note}</p> : null}
        </div>
        {rows.length > 1 ? (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => void copyAll()}>
            {copied === "all" ? <IconCheck size={14} /> : <IconCopy size={14} />}
            {copied === "all" ? "Copied both" : "Copy both"}
          </button>
        ) : null}
      </header>
      <div className="secret-copy-list">
        {rows.map((item) => (
          <label key={item.id} className="secret-copy-row">
            <span>{item.label}</span>
            <div className="secret-copy-field">
              <input
                className="secret-copy-value"
                readOnly
                value={item.value}
                onFocus={(event) => event.currentTarget.select()}
                aria-label={item.label}
              />
              <button type="button" className="btn btn-primary btn-sm" onClick={() => void copy(item.id, item.value)}>
                {copied === item.id ? <IconCheck size={14} /> : <IconCopy size={14} />}
                {copied === item.id ? "Copied" : "Copy"}
              </button>
            </div>
          </label>
        ))}
      </div>
    </section>
  );
}
