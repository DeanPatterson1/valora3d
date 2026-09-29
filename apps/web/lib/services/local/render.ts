import type { RenderJob } from "@/lib/schema";
import type { RenderShare } from "@/lib/share/types";
import { fail, ok, type Result } from "../result";
import type { RenderRequest, RenderService } from "../types";

const NOT_CONNECTED = <T>(): Result<T> => fail("not_connected", "Renderer not connected yet.");

/** Local (no backend) mode: nothing renders, nothing is charged, and there are never any jobs. */
export class LocalRenderService implements RenderService {
  async request(_input: RenderRequest): Promise<Result<RenderJob>> {
    return NOT_CONNECTED();
  }
  async get(_jobId: string): Promise<Result<RenderJob>> {
    return fail("not_found", "Render not found.");
  }
  async list(_projectId: string): Promise<Result<RenderJob[]>> {
    return ok([]);
  }
  async cancel(_jobId: string): Promise<Result<RenderJob>> {
    return NOT_CONNECTED();
  }
  async downloadUrl(_jobId: string, _file: "video" | "poster"): Promise<Result<string>> {
    return NOT_CONNECTED();
  }
  async getShare(_jobId: string): Promise<Result<RenderShare | null>> {
    return ok(null);
  }
  async share(_jobId: string, _options: { showPrompt: boolean }): Promise<Result<RenderShare>> {
    return NOT_CONNECTED();
  }
  async unshare(_jobId: string): Promise<Result<void>> {
    return ok(undefined);
  }
  subscribe(_jobId: string, _onUpdate: (job: RenderJob) => void) {
    return () => {};
  }
}
