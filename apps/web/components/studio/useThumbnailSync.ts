import { useCallback, useEffect, useRef, useState } from "react";
import { services } from "@/lib/services";
import { downscaleThumbnail } from "@/components/viewer/thumbnail";

/**
 * Drives the Viewer's `captureKey`: once after the model first mounts (the viewer waits
 * for the camera to settle) and again whenever the version count changes, deferred until
 * labour ends so the capture shows the new plan. Saving is best-effort; errors are ignored.
 */
export function useThumbnailSync(assetId: string | null, versionsLength: number, labouring: boolean) {
  const [captureKey, setCaptureKey] = useState(0);
  const seen = useRef<{ assetId: string | null; versions: number }>({ assetId: null, versions: versionsLength });

  useEffect(() => {
    if (labouring || !assetId) return;
    const prev = seen.current;
    if (prev.assetId !== assetId || prev.versions !== versionsLength) {
      seen.current = { assetId, versions: versionsLength };
      setCaptureKey((k) => k + 1);
    }
  }, [assetId, versionsLength, labouring]);

  const onThumbnail = useCallback((blob: Blob) => {
    if (!assetId) return;
    downscaleThumbnail(blob)
      .then((small) => services.projects.saveThumbnail(assetId, small))
      .catch(() => {});
  }, [assetId]);

  return { captureKey, onThumbnail };
}
