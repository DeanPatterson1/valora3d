import { Sidebar } from "@/components/layout/Sidebar";

/** The app shell: sidebar plus a scrolling main area, for every route except the landing. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
    </div>
  );
}
