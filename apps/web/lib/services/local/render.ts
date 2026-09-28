import type { RenderJob } from "@/lib/schema";
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
  subscribe(_jobId: string, _onUpdate: (job: RenderJob) => void) {
    return () => {};
  }
}
