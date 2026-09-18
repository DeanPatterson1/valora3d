/** Honest empty panel used by the studio placeholders until Tasks 23–27 replace them. */
export function Placeholder({ label, hint, className }: { label: string; hint?: string; className?: string }) {
  return (
    <div className={`flex h-full min-h-16 flex-col items-center justify-center gap-1 p-4 text-center ${className ?? ""}`}>
      <span className="text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</span>
      {hint && <span className="text-xs text-fg-muted/70">{hint}</span>}
    </div>
  );
}
