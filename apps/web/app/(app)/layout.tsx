import { Suspense } from "react";
import { AuthGate } from "@/components/auth/AuthGate";
import { Sidebar } from "@/components/layout/Sidebar";

/** The app shell: sidebar plus a scrolling main area, for every route except the landing and auth. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <div className="flex h-dvh">
          <Sidebar />
          <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
        </div>
      </AuthGate>
    </Suspense>
  );
}
