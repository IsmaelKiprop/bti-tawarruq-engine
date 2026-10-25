import { useEffect } from "react";
import { api } from "../api/client";

function controlLabel(el: Element): string {
  const labeled = el.getAttribute("aria-label") || el.getAttribute("title") || el.textContent || "";
  return labeled.replace(/\s+/g, " ").trim().slice(0, 160);
}

export function useUiAudit() {
  useEffect(() => {
    let lastKey = "";
    let lastAt = 0;

    function onClick(event: MouseEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("input[type='password'], textarea")) return;
      const control = target.closest("button, a, [role='button'], [type='submit']");
      if (!(control instanceof HTMLElement)) return;
      const label = controlLabel(control);
      if (!label) return;
      const path = window.location.pathname;
      const action = control.tagName === "A" ? "ui.nav" : "ui.click";
      const key = `${action}|${label}|${path}`;
      const now = Date.now();
      if (key === lastKey && now - lastAt < 300) return;
      lastKey = key;
      lastAt = now;
      void api.logUiAudit({ action, label, path });
    }

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);
}
