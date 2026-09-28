import { describe, expect, it } from "vitest";
import { sweepRetention, type ExpiredOutput, type ExpiredUpload, type R2Deleter, type RetentionStore } from "./retention";

const U1 = "11111111-1111-1111-1111-111111111111";
const U2 = "22222222-2222-2222-2222-222222222222";

/** In-memory mirror of the SQL retention functions (20260928150000_plan_limits_v2.sql). */
class FakeRetention implements RetentionStore {
  outputs: (ExpiredOutput & { expired: boolean })[] = [];
  uploads: (ExpiredUpload & { purged: boolean })[] = [];
  calls = { outputs: 0, uploads: 0 };
  async expiredRenderOutputs(limit: number) {
    this.calls.outputs++;
    return this.outputs.filter((o) => !o.expired).slice(0, limit).map(({ job_id, user_id }) => ({ job_id, user_id }));
  }
  async markRenderOutputsExpired(ids: string[]) {
    let n = 0;
    for (const o of this.outputs) {
      if (ids.includes(o.job_id) && !o.expired) {
        o.expired = true;
        n++;
      }
    }
    return n;
  }
  async expireUploads(limit: number) {
    this.calls.uploads++;
    return this.uploads.filter((u) => !u.purged).slice(0, limit).map(({ upload_id, user_id, r2_key }) => ({ upload_id, user_id, r2_key }));
  }
  async markUploadsPurged(ids: string[]) {
    let n = 0;
    for (const u of this.uploads) {
      if (ids.includes(u.upload_id) && !u.purged) {
        u.purged = true;
        n++;
      }
    }
    return n;
  }
}

class FakeR2 implements R2Deleter {
  deleted: string[] = [];
  failing = new Set<string>();
  async delete(key: string) {
    if (this.failing.has(key)) throw new Error("R2 DELETE failed: 500");
    this.deleted.push(key);
  }
}

describe("retention sweep", () => {
  it("deletes both output files of each expired job, then marks the job expired", async () => {
    const store = new FakeRetention();
    store.outputs = [
      { job_id: "j1", user_id: U1, expired: false },
      { job_id: "j2", user_id: U2, expired: false },
    ];
    const r2 = new FakeR2();
    const r = await sweepRetention({ store, r2, log: () => {} });
    expect(r.outputs).toEqual({ expired: 2, failed: 0 });
    expect(r2.deleted.sort()).toEqual([`r/${U1}/j1/poster.jpg`, `r/${U1}/j1/video.mp4`, `r/${U2}/j2/poster.jpg`, `r/${U2}/j2/video.mp4`]);
    expect(store.outputs.every((o) => o.expired)).toBe(true);
  });

  it("leaves a job whose delete failed unmarked, so the next sweep retries it", async () => {
    const store = new FakeRetention();
    store.outputs = [
      { job_id: "j1", user_id: U1, expired: false },
      { job_id: "j2", user_id: U1, expired: false },
    ];
    const r2 = new FakeR2();
    r2.failing.add(`r/${U1}/j2/video.mp4`);
    const r = await sweepRetention({ store, r2, log: () => {} });
    expect(r.outputs).toEqual({ expired: 1, failed: 1 });
    expect(store.outputs.find((o) => o.job_id === "j2")?.expired).toBe(false);
    r2.failing.clear();
    expect((await sweepRetention({ store, r2, log: () => {} })).outputs).toEqual({ expired: 1, failed: 0 });
  });

  it("works in bounded batches and never re-reads a row it already handled in the same run", async () => {
    const store = new FakeRetention();
    store.outputs = Array.from({ length: 7 }, (_, i) => ({ job_id: `j${i}`, user_id: U1, expired: false }));
    const r2 = new FakeR2();
    r2.failing.add(`r/${U1}/j0/video.mp4`); // stays due: must not loop on it
    const r = await sweepRetention({ store, r2, batch: 3, maxBatches: 2, log: () => {} });
    expect(r.outputs.expired + r.outputs.failed).toBeLessThanOrEqual(6);
    expect(store.calls.outputs).toBeLessThanOrEqual(2);
    expect(store.outputs.filter((o) => !o.expired).length).toBeGreaterThan(0); // the rest waits for the next cron run
  });

  it("purges claimed uploads inside the owner's prefix only", async () => {
    const store = new FakeRetention();
    store.uploads = [
      { upload_id: "a", user_id: U1, r2_key: `u/${U1}/a.glb`, purged: false },
      { upload_id: "b", user_id: U1, r2_key: `u/${U2}/b.glb`, purged: false },
    ];
    const r2 = new FakeR2();
    const r = await sweepRetention({ store, r2, log: () => {} });
    expect(r.uploads).toEqual({ purged: 1, failed: 1 });
    expect(r2.deleted).toEqual([`u/${U1}/a.glb`]);
    expect(store.uploads.find((u) => u.upload_id === "b")?.purged).toBe(false);
  });

  it("does nothing when nothing is due", async () => {
    const store = new FakeRetention();
    const r2 = new FakeR2();
    expect(await sweepRetention({ store, r2, log: () => {} })).toEqual({ outputs: { expired: 0, failed: 0 }, uploads: { purged: 0, failed: 0 } });
    expect(r2.deleted).toEqual([]);
  });
});
