"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (container: HTMLElement, options: {
    sitekey: string; action: string; theme: "dark"; size: "flexible";
    callback: (token: string) => void;
    "expired-callback": () => void; "error-callback": () => void;
  }) => string;
  remove: (id: string) => void;
};
declare global { interface Window { turnstile?: TurnstileApi } }

export const turnstileSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY?.trim();

export function Turnstile({ action, onToken }: { action: "login" | "signup" | "forgot-password"; onToken: (token: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!ready || !container.current || !window.turnstile || !turnstileSiteKey) return;
    const api = window.turnstile;
    const id = api.render(container.current, {
      sitekey: turnstileSiteKey, action, theme: "dark", size: "flexible",
      callback: (token) => { setFailed(false); onToken(token); },
      "expired-callback": () => onToken(""),
      "error-callback": () => { setFailed(true); onToken(""); },
    });
    return () => api.remove(id);
  }, [ready, action, onToken]);
  if (!turnstileSiteKey) return null;
  return (
    <div>
      <Script
        id="turnstile"
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        onReady={() => setReady(true)}
        onError={() => { setFailed(true); onToken(""); }}
      />
      <div ref={container} aria-label="Security check" />
      {failed && <p role="alert" className="text-sm text-fg-muted">Security check unavailable. <button type="button" onClick={() => window.location.reload()} className="underline focus-visible:focus-ring">Reload to try again</button>.</p>}
    </div>
  );
}
