"use client";

import { useEffect, useState } from "react";
import { services } from "@/lib/services";

/**
 * Object URL for the asset's stored thumbnail, or null while loading / when
 * there is none. The URL is revoked when the asset changes or on unmount.
 */
export function useThumbnail(assetId: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!assetId) return;
    let cancelled = false;
    let objectUrl: string | null = null;

    void services.projects.getThumbnail(assetId).then((r) => {
      if (cancelled || !r.ok || !r.value) return;
      objectUrl = URL.createObjectURL(r.value);
      setUrl(objectUrl);
    });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setUrl(null);
    };
  }, [assetId]);

  return url;
}
