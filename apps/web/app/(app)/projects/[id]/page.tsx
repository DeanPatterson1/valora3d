"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { StudioShell } from "@/components/studio/StudioShell";
import { useStudioStore } from "@/lib/stores/studio";

export default function StudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const notFound = useStudioStore((s) => s.notFound);

  useEffect(() => {
    void useStudioStore.getState().open(id);
    return () => useStudioStore.getState().reset();
  }, [id]);

  useEffect(() => {
    if (notFound) router.replace("/projects?notice=not_found");
  }, [notFound, router]);

  return <StudioShell />;
}
