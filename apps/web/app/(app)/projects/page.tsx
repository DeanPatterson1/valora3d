import { Suspense } from "react";
import type { Metadata } from "next";
import { Dashboard } from "@/components/dashboard/Dashboard";

export const metadata: Metadata = { title: "Projects", description: "Manage your Valora3D projects and start a new cinematic shot.", robots: { index: false, follow: false } };

export default function ProjectsPage() {
  return (
    <Suspense fallback={null}>
      <Dashboard />
    </Suspense>
  );
}
