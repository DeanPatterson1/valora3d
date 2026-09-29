import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { presignLifetimes } from "@/lib/render/contract";
import { INPUT_FAILURE_DAILY_CAP, RENDER_DAILY_CAP, UPLOAD_DAILY_CAP } from "@/lib/usageLimits";
import { R2Storage } from "./r2";
import {
  RENDER_PUT_WINDOW_MS,
  UPLOAD_PUT_WINDOW_MS,
  drainStoragePurges,
  enqueueAccountPurge,
  isPurgeTarget,
  type PurgeEntry,
  type PurgeStorage,
  type PurgeStore,
} from "./storagePurge";

const U = "11111111-1111-4111-8111-111111111111";
const J = "22222222-2222-4222-8222-222222222222";
const SQL = readFileSync(join(import.meta.dirname, "../../supabase/migrations/20260929200000_storage_security.sql"), "utf8").replace(/\r\n/g, "\n");

class FakeQueue implements PurgeStore {
  entries: (PurgeEntry & { notBefore: number })[] = [];
  completed: number[] = [];
  released: { ids: number[]; error: string }[] = [];
  seq = 0;
  async enqueue(userId: string, target: string, _reason: string, notBefore?: Date) {
    this.entries.push({ id: ++this.seq, user_id: userId, target, notBefore: notBefore?.getTime() ?? 0 });
  }
  async claim(limit: number, userId?: string) {
    return this.entries.filter((e) => e.notBefore <= Date.now() && (!userId || e.user_id === userId)).slice(0, limit);
  }
  async complete(ids: number[]) {
    this.completed.push(...ids);
  }
  async release(ids: number[], error: string) {
    this.released.push({ ids, error });
  }
}

/** A bucket as a sorted key list; each LIST page and each DELETE costs one op, like R2Storage. */
class FakeBucket implements PurgeStorage {
  constructor(public keys: string[], public failOn: string | null = null) {}
  async delete(key: string) {
    if (key === this.failOn) throw new Error("R2 DELETE failed: 503");
    this.keys = this.keys.filter((k) => k !== key);
  }
  async deletePrefixBounded(prefix: string, maxOps: number) {
    let ops = 1;
    let removed = 0;
    for (const k of this.keys.filter((x) => x.startsWith(prefix))) {
      if (ops >= maxOps) return { removed, complete: false, ops };
      ops++;
      await this.delete(k);
      removed++;
    }
    return { removed, complete: true, ops };
  }
}

describe("storage purge queue", () => {
  it("accepts only the site's own shapes, inside the owner's prefix", () => {
    expect(isPurgeTarget(`u/${U}/`, U)).toBe(true);
    expect(isPurgeTarget(`r/${U}/`, U)).toBe(true);
    expect(isPurgeTarget(`r/${U}/${J}/`, U)).toBe(true);
    expect(isPurgeTarget(`u/${U}/${J}.glb`, U)).toBe(true);
    for (const bad of ["", "/", "u/", "r/", `u/${J}/`, "samples/", `r/${U}/${J}/video.mp4`, `u/${U}/../x/`, `x/${U}/`]) {
      expect(isPurgeTarget(bad, U), bad).toBe(false);
    }
  });

  it("queues the account's model and render prefixes now and after every presigned PUT has expired", async () => {
    const q = new FakeQueue();
    await enqueueAccountPurge(q, U, 1_000);
    expect(q.entries.map((e) => [e.target, e.notBefore])).toEqual([
      [`u/${U}/`, 0],
      [`r/${U}/`, 0],
      [`u/${U}/`, 1_000 + UPLOAD_PUT_WINDOW_MS],
      [`r/${U}/`, 1_000 + RENDER_PUT_WINDOW_MS],
    ]);
  });

  it("H1: deletes models AND render outputs; an R2 failure keeps the entry for the sweep", async () => {
    const q = new FakeQueue();
    await enqueueAccountPurge(q, U, Date.now());
    const bucket = new FakeBucket([`u/${U}/a.glb`, `r/${U}/${J}/video.mp4`, `r/${U}/${J}/poster.jpg`, `r/${J}/other.mp4`]);
    const r = await drainStoragePurges({ store: q, r2: bucket, log: () => {} }, { budget: 100, userId: U });
    expect(bucket.keys).toEqual([`r/${J}/other.mp4`]);
    expect(r).toMatchObject({ done: 2, removed: 3, failed: 0 });
    expect(q.completed).toEqual([1, 2]);

    const q2 = new FakeQueue();
    await q2.enqueue(U, `u/${U}/${J}.glb`, "upload_deleted");
    const failing = new FakeBucket([`u/${U}/${J}.glb`], `u/${U}/${J}.glb`);
    const r2 = await drainStoragePurges({ store: q2, r2: failing, log: () => {} }, { budget: 100 });
    expect(r2).toMatchObject({ done: 0, failed: 1 });
    expect(q2.completed).toEqual([]);
    expect(q2.released).toEqual([{ ids: [1], error: "R2 delete failed" }]);
  });

  it("stays inside its request budget and continues later (paginated, never all at once)", async () => {
    const q = new FakeQueue();
    await q.enqueue(U, `r/${U}/`, "account_deleted");
    await q.enqueue(U, `u/${U}/`, "account_deleted");
    const bucket = new FakeBucket(Array.from({ length: 10 }, (_, i) => `r/${U}/${J}/f${i}`));
    const r = await drainStoragePurges({ store: q, r2: bucket }, { budget: 5 });
    expect(r).toMatchObject({ done: 0, pending: 2, removed: 4 });
    expect(q.released[0].ids).toEqual([1, 2]);
    expect(bucket.keys).toHaveLength(6);
  });

  it("keeps the TS windows, caps and SQL in step", () => {
    expect(RENDER_PUT_WINDOW_MS).toBe(presignLifetimes("final").putSeconds * 1000);
    expect(SQL).toContain("when 'preview' then interval '24 hours 50 minutes' else interval '26 hours 30 minutes'");
    expect(presignLifetimes("preview").putSeconds).toBe((24 * 60 + 50) * 60);
    expect(presignLifetimes("final").putSeconds).toBe((26 * 60 + 30) * 60);
    expect(SQL).toContain(`upload_daily_cap() returns integer\nlanguage sql immutable parallel safe set search_path = '' as $$ select ${UPLOAD_DAILY_CAP} $$`);
    expect(SQL).toContain(`render_daily_cap() returns integer\nlanguage sql immutable parallel safe set search_path = '' as $$ select ${RENDER_DAILY_CAP} $$`);
    expect(SQL).toContain(`input_failure_daily_cap() returns integer\nlanguage sql immutable parallel safe set search_path = '' as $$ select ${INPUT_FAILURE_DAILY_CAP} $$`);
    expect(SQL).not.toMatch(/security definer/i);
    expect(SQL).toContain("revoke delete on public.projects from authenticated");
  });
});

describe("R2Storage.deletePrefixBounded", () => {
  const config = { accountId: "acct", bucket: "valora", accessKeyId: "id", secretAccessKey: "secret" };
  const bucket = (keys: string[], pageSize = 2) => {
    const deleted: string[] = [];
    const lists: string[] = [];
    const fake = vi.fn(async (req: RequestInfo | URL) => {
      const r = req as Request;
      const u = new URL(r.url);
      if (r.method === "DELETE") {
        deleted.push(decodeURIComponent(u.pathname).replace("/valora/", ""));
        return new Response(null, { status: 204 });
      }
      lists.push(u.searchParams.get("prefix") ?? "");
      const left = keys.filter((k) => k.startsWith(u.searchParams.get("prefix") ?? "") && !deleted.includes(k));
      const page = left.slice(0, pageSize);
      const more = left.length > pageSize;
      const xml = `<ListBucketResult>${page.map((k) => `<Key>${k}</Key>`).join("")}<IsTruncated>${more}</IsTruncated>${more ? "<NextContinuationToken>a&amp;b</NextContinuationToken>" : ""}</ListBucketResult>`;
      return new Response(xml, { status: 200 });
    }) as unknown as typeof fetch;
    return { r2: new R2Storage(config, fake), deleted, lists, fake };
  };

  it("pages through a prefix and counts every request", async () => {
    const b = bucket([`r/${U}/a`, `r/${U}/b`, `r/${U}/c`]);
    expect(await b.r2.deletePrefixBounded(`r/${U}/`, 100)).toEqual({ removed: 3, complete: true, ops: 5 });
    expect(b.deleted).toEqual([`r/${U}/a`, `r/${U}/b`, `r/${U}/c`]);
  });

  it("stops at the budget and reports it incomplete", async () => {
    const b = bucket([`r/${U}/a`, `r/${U}/b`, `r/${U}/c`]);
    expect(await b.r2.deletePrefixBounded(`r/${U}/`, 2)).toEqual({ removed: 1, complete: false, ops: 2 });
  });

  it("refuses an empty or open prefix (it would list the whole bucket)", async () => {
    const b = bucket([]);
    await expect(b.r2.deletePrefixBounded("", 10)).rejects.toThrow();
    await expect(b.r2.deletePrefixBounded("u", 10)).rejects.toThrow();
    expect(b.fake).not.toHaveBeenCalled();
  });
});
