"use client";

import { useEffect } from "react";
import { reportClientError } from "@/lib/errors/report";

/**
 * Uncaught errors and rejections outside React's error boundaries, reported with fixed fields only
 * (lib/errors/report.ts). Only errors thrown by our own scripts count: extensions and third-party scripts (Paddle,
 * Turnstile) are skipped, and a rejection must carry a real Error.
 */
export function ErrorReporter() {
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      if (!e.error || !(e.error instanceof Error)) return;
      if (e.filename && !e.filename.startsWith(window.location.origin)) return;
      reportClientError("window", e.error);
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      if (e.reason instanceof Error) reportClientError("promise", e.reason);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);
  return null;
}
