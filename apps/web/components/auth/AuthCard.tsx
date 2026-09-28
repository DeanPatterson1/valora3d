import Link from "next/link";
import { services } from "@/lib/services";

export type AuthCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Switch line under the card: "No account? Sign up". */
  footer?: { text: string; linkLabel: string; href: string };
};

/**
 * A compact auth panel using the site's neutral surfaces and white actions.
 */
export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="flex w-full max-w-[28rem] flex-col items-stretch gap-5 rounded-[24px] border border-line bg-bg-1 p-5 sm:p-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg">{title}</h1>
        {subtitle && <p className="text-sm text-fg-muted">{subtitle}</p>}
      </div>
      {services.backend === "local" && (
        <p className="border-l-2 border-fg-muted/40 pl-3 text-xs leading-relaxed text-fg-muted">
          Prototype: accounts live in this browser only. No email is sent and passwords are not stored.
        </p>
      )}
      {children}
      {footer && (
        <p className="text-center text-sm text-fg-muted">
          {footer.text}{" "}
          <Link href={footer.href} className="rounded-sm text-fg underline-offset-4 hover:underline focus-visible:focus-ring">
            {footer.linkLabel}
          </Link>
        </p>
      )}
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
