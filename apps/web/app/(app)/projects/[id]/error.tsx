"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui";

export default function StudioError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <h1 className="tracking-tight text-2xl font-semibold text-fg">Something went wrong in the studio</h1>
      <p className="max-w-md text-sm text-fg-muted">
        Your project and versions are saved in this browser. Try again, or go back to your projects.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button variant="primary" onClick={reset}>Try again</Button>
        <Link
          href="/projects"
          className="inline-flex h-10 items-center rounded-md border border-line bg-bg-2 px-4 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
        >
          Back to projects
        </Link>
      </div>
    </div>
  );
}
