import { Suspense } from "react";
import { RendersScreen } from "@/components/admin/screens";

export default function AdminRendersPage() {
  return (
    <Suspense fallback={null}>
      <RendersScreen />
    </Suspense>
  );
}
