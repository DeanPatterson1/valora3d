/* eslint-disable @typescript-eslint/no-unused-vars -- stub keeps the interface signatures but ignores every input */
import type { RenderJob } from "@/lib/schema";
import { fail, type Result } from "../result";
import type { RenderService } from "../types";

const NOT_CONNECTED = (): Result<RenderJob> => fail("not_connected", "Renderer not connected yet.");

export class LocalRenderService implements RenderService {
  async requestPreview(_projectId: string, _versionId: string) {
    return NOT_CONNECTED();
  }
  async requestFinal(_projectId: string, _versionId: string, _target: "local" | "cloud") {
    return NOT_CONNECTED();
  }
  subscribe(_jobId: string, _onUpdate: (job: RenderJob) => void) {
    return () => {};
  }
}
