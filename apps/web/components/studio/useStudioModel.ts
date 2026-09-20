import { useEffect, useState } from "react";
import type * as THREE from "three";
import { services, type ServiceError } from "@/lib/services";
import type { Asset } from "@/lib/schema";
import { loadModel } from "@/components/viewer/loadModel";
import { useEditorStore } from "@/lib/stores/editor";

export type StudioModel = {
  root: THREE.Object3D | null;
  notices: string[];
  error: ServiceError | null;
  loading: boolean;
};

const IDLE: StudioModel = { root: null, notices: [], error: null, loading: false };
const LOADING: StudioModel = { ...IDLE, loading: true };

type Resolved = { assetId: string; root: THREE.Object3D | null; notices: string[]; error: ServiceError | null };

/**
 * Loads the project's model for the viewer: samples by URL, uploads from IndexedDB.
 * When `blobMissing` nothing is loaded; the shell shows the re-upload state instead.
 */
export function useStudioModel(asset: Asset | null, blobMissing: boolean): StudioModel {
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const assetId = asset?.id ?? null;
  const projectId = asset?.projectId ?? null;
  const sampleUrl = asset?.sampleUrl ?? null;
  const format = asset?.format ?? null;
  const wanted = assetId !== null && format !== null && !blobMissing;

  useEffect(() => {
    if (!wanted || !assetId || !format || !projectId) return;
    let cancelled = false;
    (async () => {
      let source: Blob | string | null = sampleUrl;
      if (!source) {
        // Re-read the asset record so a stale closure never loads the wrong blob.
        const a = await services.projects.getAsset(assetId);
        if (cancelled) return;
        if (!a.ok) { setResolved({ assetId, root: null, notices: [], error: a.error }); return; }
        const b = await services.projects.getAssetBlob(a.value);
        if (cancelled) return;
        if (!b.ok) { setResolved({ assetId, root: null, notices: [], error: b.error }); return; }
        source = b.value;
      }
      if (!source) {
        setResolved({ assetId, root: null, notices: [], error: { code: "blob_missing", message: "The model file is missing from this browser." } });
        return;
      }
      const r = await loadModel(source, format);
      if (cancelled) return;
      if (r.ok) {
        // Replay the user's geometry edits and switch to clay before the viewer ever
        // sees the root, so the first frame is already the edited, untextured model.
        useEditorStore.getState().attach(projectId, r.value.root);
        setResolved({ assetId, root: r.value.root, notices: r.value.notices, error: null });
      } else setResolved({ assetId, root: null, notices: [], error: r.error });
    })();
    return () => { cancelled = true; };
  }, [wanted, assetId, projectId, sampleUrl, format]);

  // Editing state belongs to one open model; drop it when the studio unmounts.
  useEffect(() => () => useEditorStore.getState().detach(), []);

  if (!wanted) return IDLE;
  // Never hand the viewer a model from a previous asset.
  if (!resolved || resolved.assetId !== assetId) return LOADING;
  return { root: resolved.root, notices: resolved.notices, error: resolved.error, loading: false };
}
