import { useCallback, useEffect, useRef, useState } from "react";
import { services } from "@/lib/services";
import { downscaleThumbnail } from "@/components/viewer/thumbnail";

/**
 * Drives the Viewer's `captureKey`: one bump per appended version, deferred until labour
 * ends so the capture shows the new plan. The model-load capture is the viewer's own
 * (`ThumbnailCapture` arms itself when its `modelKey` changes), so it is not repeated
 * here. Re-renders, labour toggles, selection changes and slider previews never bump it:
 * every capture reads the drawing buffer back, which stalls the GPU. Saving is
 * best-effort; errors are ignored.
 */
export function useThumbnailSync(assetId: string | null, versionsLength: number, labouring: boolean) {
  const [captureKey, setCaptureKey] = useState(0);
  const seen = useRef<{ assetId: string | null; versions: number }>({ assetId, versions: versionsLength });

  useEffect(() => {
    if (labouring || !assetId) return;
    const prev = seen.current;
    // A new model starts its own count; only appends on the same model ask for a capture.
    const appended = prev.assetId === assetId && versionsLength > prev.versions;
    seen.current = { assetId, versions: versionsLength };
    if (appended) setCaptureKey((k) => k + 1);
  }, [assetId, versionsLength, labouring]);

  const onThumbnail = useCallback((blob: Blob) => {
    if (!assetId) return;
    downscaleThumbnail(blob)
      .then((small) => services.projects.saveThumbnail(assetId, small))
      .catch(() => {});
  }, [assetId]);

  return { captureKey, onThumbnail };
}
