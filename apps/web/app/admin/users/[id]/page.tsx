import { UserDetailScreen } from "@/components/admin/screens";

export default async function AdminUserPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <UserDetailScreen id={id} />;
}
