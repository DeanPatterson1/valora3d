"use client";

import { useState } from "react";
import { Button } from "@/components/ui";
import type { AuthProvider } from "@/lib/services";

function GoogleGlyph() {
  // Monochrome "G": the app has no accent colour, so brand colours stay out.
  return (
    <svg aria-hidden viewBox="0 0 24 24" fill="currentColor">
      <path d="M21.6 12.23c0-.68-.06-1.33-.17-1.96H12v3.7h5.38a4.6 4.6 0 0 1-2 3.02v2.5h3.23c1.9-1.74 2.99-4.31 2.99-7.26Z" />
      <path d="M12 21.8c2.7 0 4.96-.9 6.61-2.42l-3.23-2.5c-.9.6-2.04.95-3.38.95-2.6 0-4.8-1.75-5.59-4.11H3.08v2.58A9.99 9.99 0 0 0 12 21.8Z" />
      <path d="M6.41 13.72a6.02 6.02 0 0 1 0-3.84V7.3H3.08a10 10 0 0 0 0 9l3.33-2.58Z" />
      <path d="M12 6.16c1.47 0 2.79.5 3.83 1.5l2.87-2.87A9.98 9.98 0 0 0 12 2.2a9.99 9.99 0 0 0-8.92 5.1l3.33 2.58c.79-2.36 2.99-4.11 5.59-4.11Z" />
    </svg>
  );
}

function AppleGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" fill="currentColor">
      <path d="M16.37 12.69c.02 2.9 2.54 3.86 2.57 3.87-.02.07-.4 1.38-1.33 2.72-.8 1.17-1.63 2.33-2.94 2.35-1.29.02-1.7-.76-3.17-.76-1.47 0-1.93.74-3.15.79-1.26.05-2.22-1.26-3.03-2.42C3.67 16.86 2.4 12.53 4.1 9.6c.84-1.45 2.35-2.37 3.99-2.4 1.24-.02 2.42.84 3.17.84.76 0 2.19-1.04 3.69-.89.63.03 2.39.25 3.53 1.92-.09.06-2.1 1.23-2.08 3.62ZM13.94 5.61c.67-.81 1.12-1.94 1-3.07-.97.04-2.14.65-2.83 1.46-.62.72-1.16 1.87-1.02 2.97 1.08.08 2.18-.55 2.85-1.36Z" />
    </svg>
  );
}

const PROVIDERS: { id: AuthProvider; label: string; icon: React.ReactNode }[] = [
  { id: "google", label: "Continue with Google", icon: <GoogleGlyph /> },
  { id: "apple", label: "Continue with Apple", icon: <AppleGlyph /> },
];

export type ProviderButtonsProps = {
  onChoose: (provider: AuthProvider) => Promise<void>;
  disabled?: boolean;
};

export function ProviderButtons({ onChoose, disabled }: ProviderButtonsProps) {
  const [pending, setPending] = useState<AuthProvider | null>(null);
  const choose = async (id: AuthProvider) => {
    setPending(id);
    try {
      await onChoose(id);
    } finally {
      setPending(null);
    }
  };
  return (
    <div className="flex flex-col gap-2.5">
      {PROVIDERS.map((p) => (
        <Button
          key={p.id}
          size="lg"
          icon={p.icon}
          loading={pending === p.id}
          disabled={disabled || (pending !== null && pending !== p.id)}
          onClick={() => void choose(p.id)}
          className="h-12 w-full justify-start gap-3 px-4 text-fg"
        >
          {p.label}
        </Button>
      ))}
    </div>
  );
}
