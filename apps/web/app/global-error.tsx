"use client";

import { Inter } from "next/font/google";
import { useEffect, useRef } from "react";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export default function GlobalError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const reported = useRef(false);
  useEffect(() => {
    if (reported.current) return;
    reported.current = true;
    // Fixed payload only. Raw errors, stacks and the current URL may contain private data.
    void fetch("/api/client-errors", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "global_error" }), keepalive: true, credentials: "omit",
    }).catch(() => { /* Reporting must never prevent recovery. */ });
  }, []);
  return (
    <html lang="en">
      <body className={inter.className} style={{ margin: 0, background: "#0d0d0d", color: "#ffffff" }}>
        <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center gap-5 px-6 py-20">
          <p className="text-sm text-fg-muted">Valora3D</p>
          <h1 className="text-4xl font-semibold tracking-tight">Something went wrong</h1>
          <p className="text-base leading-relaxed text-fg-muted">Please try again. If the problem continues, email <a href="mailto:support@valora3d.com" className="text-fg underline focus-visible:focus-ring">support@valora3d.com</a>.</p>
          <div className="mt-3 flex flex-wrap gap-4">
            <button type="button" onClick={retry} className="h-11 rounded-full bg-primary px-5 text-sm font-medium text-primary-fg focus-visible:focus-ring">Try again</button>
            {/* A full navigation also recovers a broken root layout. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/" className="inline-flex h-11 items-center rounded-full border border-line px-5 text-sm focus-visible:focus-ring">Back to home</a>
          </div>
        </main>
      </body>
    </html>
  );
}
