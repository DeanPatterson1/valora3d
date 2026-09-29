import { Suspense } from "react";
import { AuthGate } from "@/components/auth/AuthGate";
import { PastDueBanner } from "@/components/account/PastDueBanner";
import { FeedbackHost } from "@/components/feedback/FeedbackDialog";
import { Sidebar } from "@/components/layout/Sidebar";

/** The app shell: sidebar plus a scrolling main area, for every route except the landing and auth. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <div className="flex h-dvh">
          <a href="#main-content" className="sr-only z-[60] rounded-full bg-primary px-5 py-3 text-primary-fg focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Skip to content</a>
          <Sidebar />
          <main id="main-content" tabIndex={-1} className="flex min-w-0 flex-1 flex-col overflow-auto outline-none">
            <PastDueBanner />
            {children}
          </main>
        </div>
        <FeedbackHost />
      </AuthGate>
    </Suspense>
  );
}
