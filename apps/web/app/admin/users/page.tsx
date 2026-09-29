import { Suspense } from "react";
import { UsersScreen } from "@/components/admin/screens";

export default function AdminUsersPage() {
  return (
    <Suspense fallback={null}>
      <UsersScreen />
    </Suspense>
  );
}
