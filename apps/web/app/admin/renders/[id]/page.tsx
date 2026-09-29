import { RenderDetailScreen } from "@/components/admin/screens";

export default async function AdminRenderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RenderDetailScreen id={id} />;
}
