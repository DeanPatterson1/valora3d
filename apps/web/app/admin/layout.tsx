import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AdminLocalNotice, AdminShell } from "@/components/admin/AdminShell";
import { publicSupabaseConfig } from "@/lib/env";
import { requireAdmin } from "@/lib/server/admin";

export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false, nocache: true } };
export const dynamic = "force-dynamic";

/**
 * The owner console. The proxy already answers non-admins with a 404 (lib/supabase/proxy.ts); this is the second,
 * server-side check. Every /api/admin route checks a third time with the service role (lib/server/admin.ts).
 */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  if (!publicSupabaseConfig()) {
    return (
      <AdminShell current={null} nav={false}>
        <AdminLocalNotice />
      </AdminShell>
    );
  }
  const ctx = await requireAdmin();
  if (ctx instanceof Response) notFound();
  return <AdminShell>{children}</AdminShell>;
}
