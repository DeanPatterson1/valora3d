"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Skeleton } from "@/components/ui";
import { useAuthStore } from "@/lib/stores/auth";

/** What the app shell shows while the session is being read: the sidebar frame and a blank main area. */
function ShellSkeleton() {
  return (
    <div className="flex h-dvh" aria-busy aria-label="Loading">
      <div className="hidden w-[260px] shrink-0 flex-col gap-2 bg-bg-1 p-2 md:flex">
        <div className="flex h-11 items-center pl-2.5">
          <Skeleton className="h-4 w-28" />
        </div>
        <Skeleton className="h-9 w-full" />
        <div className="mt-4 flex flex-col gap-1.5 px-2.5">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      </div>
      <div className="flex-1" />
    </div>
  );
}

/**
 * Wraps every app route: reads the session on mount, holds a skeleton until it is
 * known, and sends signed-out visitors to /login with the page they wanted.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const loaded = useAuthStore((s) => s.loaded);
  const refresh = useAuthStore((s) => s.refresh);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!loaded || user) return;
    const search = params.toString();
    const next = search ? `${pathname}?${search}` : pathname;
    router.replace(`/login?next=${encodeURIComponent(next)}`);
  }, [loaded, user, pathname, params, router]);

  if (!loaded || !user) return <ShellSkeleton />;
  return <>{children}</>;
}
