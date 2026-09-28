import { describe, expect, it, vi } from "vitest";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { R2Storage } from "@/lib/server/r2";
import { verifyUploadedObject, type CompletionStorage } from "./complete";
import { checkGlbHeader, isAllowedSampleUrl, uploadKey, validateDeclaredUpload } from "./validate";

function glbHeader(length: number, magic = "glTF", version = 2): Uint8Array {
  const bytes = new Uint8Array(12);
  for (let i = 0; i < 4; i++) bytes[i] = magic.charCodeAt(i);
  const view = new DataView(bytes.buffer);
  view.setUint32(4, version, true);
  view.setUint32(8, length, true);
  return bytes;
}

describe("validateDeclaredUpload", () => {
  it("accepts a .glb within the cap", () => {
    const r = validateDeclaredUpload({ fileName: " Car.GLB ", sizeBytes: 1024 });
    expect(r).toEqual({ ok: true, value: { fileName: "Car.GLB", sizeBytes: 1024, sha256: null } });
  });
  it.each(["car.gltf", "car.fbx", "car.obj", "car.blend", "car.glb.zip", ".glb"])("refuses %s", (fileName) => {
    const r = validateDeclaredUpload({ fileName, sizeBytes: 10 });
    expect(!r.ok && r.error.code).toBe("unsupported_format");
  });
  it("refuses path separators and control characters in the name", () => {
    expect(validateDeclaredUpload({ fileName: "../x.glb", sizeBytes: 10 }).ok).toBe(false);
    expect(validateDeclaredUpload({ fileName: "a\u0000.glb", sizeBytes: 10 }).ok).toBe(false);
  });
  it("refuses empty, fractional and oversized files; accepts exactly the cap", () => {
    expect(!validateDeclaredUpload({ fileName: "a.glb", sizeBytes: 0 }).ok).toBe(true);
    expect(!validateDeclaredUpload({ fileName: "a.glb", sizeBytes: 1.5 }).ok).toBe(true);
    const big = validateDeclaredUpload({ fileName: "a.glb", sizeBytes: MAX_UPLOAD_BYTES + 1 });
    expect(!big.ok && big.error.code).toBe("too_large");
    expect(validateDeclaredUpload({ fileName: "a.glb", sizeBytes: MAX_UPLOAD_BYTES }).ok).toBe(true);
  });
  it("normalises a valid sha256 and refuses a malformed one", () => {
    const sha = "A".repeat(64);
    const r = validateDeclaredUpload({ fileName: "a.glb", sizeBytes: 1, sha256: sha });
    expect(r.ok && r.value.sha256).toBe("a".repeat(64));
    expect(validateDeclaredUpload({ fileName: "a.glb", sizeBytes: 1, sha256: "xyz" }).ok).toBe(false);
  });
});

describe("keys and samples", () => {
  it("puts every object under the owner's prefix", () => {
    expect(uploadKey("user-1", "abc")).toBe("u/user-1/abc.glb");
  });
  it("allows only shipped .glb samples", () => {
    expect(isAllowedSampleUrl("/samples/toycar.glb")).toBe(true);
    expect(isAllowedSampleUrl("/samples/../secret.glb")).toBe(false);
    expect(isAllowedSampleUrl("https://evil.example/samples/x.glb")).toBe(false);
    expect(isAllowedSampleUrl("/samples/x.fbx")).toBe(false);
    expect(isAllowedSampleUrl("/samples/%2e%2e/x.glb")).toBe(false);
  });
});

describe("checkGlbHeader", () => {
  it("accepts a glTF 2 header whose length matches", () => {
    expect(checkGlbHeader(glbHeader(500), 500)).toBeNull();
  });
  it("rejects wrong magic, version, length and short input", () => {
    expect(checkGlbHeader(glbHeader(500, "PK\u0003\u0004"), 500)).toMatch(/not a binary glTF/);
    expect(checkGlbHeader(glbHeader(500, "glTF", 1), 500)).toMatch(/2\.0/);
    expect(checkGlbHeader(glbHeader(499), 500)).toMatch(/length/);
    expect(checkGlbHeader(new Uint8Array(4), 500)).toMatch(/too short/);
  });
});

describe("verifyUploadedObject", () => {
  const storage = (size: number | null, header: Uint8Array): CompletionStorage & { deleted: string[] } => {
    const deleted: string[] = [];
    return {
      deleted,
      headSize: vi.fn(async () => size),
      getRange: vi.fn(async () => header),
      delete: vi.fn(async (k: string) => void deleted.push(k)),
    };
  };

  it("marks a real glb ready", async () => {
    const s = storage(500, glbHeader(500));
    expect(await verifyUploadedObject(s, "u/x/a.glb", 500)).toEqual({ status: "ready", sizeBytes: 500 });
    expect(s.deleted).toEqual([]);
  });
  it("reports a missing object without deleting anything", async () => {
    const s = storage(null, glbHeader(0));
    expect(await verifyUploadedObject(s, "k", 500)).toEqual({ status: "missing" });
    expect(s.deleted).toEqual([]);
  });
  it("rejects and deletes a size mismatch", async () => {
    const s = storage(600, glbHeader(600));
    const r = await verifyUploadedObject(s, "k", 500);
    expect(r.status).toBe("rejected");
    expect(s.deleted).toEqual(["k"]);
  });
  it("rejects and deletes an object over the cap even if declared", async () => {
    const s = storage(MAX_UPLOAD_BYTES + 1, glbHeader(0));
    expect((await verifyUploadedObject(s, "k", MAX_UPLOAD_BYTES + 1)).status).toBe("rejected");
    expect(s.getRange).not.toHaveBeenCalled();
  });
  it("rejects and deletes a renamed non-glb", async () => {
    const s = storage(500, glbHeader(500, "PK\u0003\u0004"));
    const r = await verifyUploadedObject(s, "k", 500);
    expect(r).toMatchObject({ status: "rejected" });
    expect(s.deleted).toEqual(["k"]);
  });
});

describe("R2Storage", () => {
  const config = { accountId: "acct", bucket: "valora", accessKeyId: "AKID", secretAccessKey: "secret" };

  it("presigns a create-only PUT that pins the content length", async () => {
    const put = await new R2Storage(config).presignPut("u/user-1/a.glb", 1234, 600);
    expect(put.headers).toEqual({ "If-None-Match": "*" });
    const url = new URL(put.url);
    expect(url.searchParams.get("X-Amz-SignedHeaders")).toContain("if-none-match");
    expect(url.host).toBe("acct.r2.cloudflarestorage.com");
    expect(url.pathname).toBe("/valora/u/user-1/a.glb");
    expect(url.searchParams.get("X-Amz-Expires")).toBe("600");
    expect(url.searchParams.get("X-Amz-SignedHeaders")).toContain("content-length");
    expect(url.searchParams.get("X-Amz-Signature")).toMatch(/^[0-9a-f]{64}$/);
  });

  it("reads a ranged header and treats 404 as missing", async () => {
    const seen: Request[] = [];
    const fake = vi.fn(async (req: RequestInfo | URL) => {
      const r = req as Request;
      seen.push(r);
      if (r.method === "HEAD") return new Response(null, { status: 404 });
      return new Response(glbHeader(12).buffer as ArrayBuffer, { status: 206 });
    }) as unknown as typeof fetch;
    const r2 = new R2Storage(config, fake);
    expect(await r2.headSize("u/x/a.glb")).toBeNull();
    expect(await r2.getRange("u/x/a.glb", 0, 11)).toHaveLength(12);
    expect(seen[1].headers.get("range")).toBe("bytes=0-11");
    expect(seen[1].headers.get("authorization")).toMatch(/^AWS4-HMAC-SHA256/);
  });

  it("deletes every key under a prefix across pages", async () => {
    const deleted: string[] = [];
    const fake = vi.fn(async (req: RequestInfo | URL) => {
      const r = req as Request;
      const u = new URL(r.url);
      if (r.method === "DELETE") {
        deleted.push(decodeURIComponent(u.pathname));
        return new Response(null, { status: 204 });
      }
      const page2 = u.searchParams.get("continuation-token") === "t2";
      const xml = page2
        ? "<ListBucketResult><Key>u/x/b.glb</Key><IsTruncated>false</IsTruncated></ListBucketResult>"
        : "<ListBucketResult><Key>u/x/a.glb</Key><IsTruncated>true</IsTruncated><NextContinuationToken>t2</NextContinuationToken></ListBucketResult>";
      return new Response(xml, { status: 200 });
    }) as unknown as typeof fetch;
    expect(await new R2Storage(config, fake).deletePrefix("u/x/")).toBe(2);
    expect(deleted).toEqual(["/valora/u/x/a.glb", "/valora/u/x/b.glb"]);
  });
});
