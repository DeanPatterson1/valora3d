import Link from "next/link";

export type AuthCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Switch line under the card: "No account? Sign up". */
  footer: { text: string; linkLabel: string; href: string };
};

/**
 * The centred auth column: a big greeting, the form, then a quiet switch line and
 * the legal line. No border or panel; the page background is the card.
 */
export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="flex w-full max-w-[22rem] flex-col items-stretch gap-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">{title}</h1>
        {subtitle && <p className="text-sm text-fg-muted">{subtitle}</p>}
      </div>
      {children}
      <p className="text-center text-sm text-fg-muted">
        {footer.text}{" "}
        <Link href={footer.href} className="rounded-sm text-fg underline-offset-4 hover:underline focus-visible:focus-ring">
          {footer.linkLabel}
        </Link>
      </p>
      <p className="text-center text-xs text-fg-muted/70">
        Prototype: accounts live in this browser only. No email is sent and passwords are not stored.
      </p>
    </div>
  );
}

/** The "OR" rule between the email form and the provider buttons. */
export function OrDivider() {
  return (
    <div className="flex items-center gap-3" aria-hidden>
      <span className="h-px flex-1 bg-line" />
      <span className="text-xs text-fg-muted">OR</span>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}
