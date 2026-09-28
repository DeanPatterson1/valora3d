import { AwsClient } from "aws4fetch";
import type { R2Config } from "@/lib/env";

/**
 * R2 through its S3 API, signed with aws4fetch (Web Crypto + fetch, so it runs on Workers
 * without the AWS SDK). Server-only: holds the R2 secret.
 */
export class R2Storage {
  private readonly aws: AwsClient;
  private readonly base: string;

  constructor(config: R2Config, fetchImpl?: typeof fetch) {
    this.aws = new AwsClient({
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
      service: "s3",
      region: "auto",
    });
    this.base = `https://${config.accountId}.r2.cloudflarestorage.com/${config.bucket}`;
    if (fetchImpl) this.fetchImpl = fetchImpl;
  }

  private fetchImpl: typeof fetch = (...args) => fetch(...args);

  private url(key: string): string {
    return `${this.base}/${key.split("/").map(encodeURIComponent).join("/")}`;
  }

  /**
   * A presigned PUT for exactly `sizeBytes` bytes that can only CREATE the object.
   * Content-Length and `If-None-Match: *` are signed, so R2 refuses another size and refuses to
   * overwrite: once /complete has verified the object, the still-valid URL cannot replace it.
   * The browser must send `headers` with the PUT (the bucket's CORS rule allows If-None-Match).
   */
  async presignPut(key: string, sizeBytes: number, expiresSeconds = 600): Promise<{ url: string; headers: Record<string, string> }> {
    const url = new URL(this.url(key));
    url.searchParams.set("X-Amz-Expires", String(expiresSeconds));
    const headers = { "If-None-Match": "*" };
    const signed = await this.aws.sign(url.toString(), {
      method: "PUT",
      headers: { ...headers, "Content-Length": String(sizeBytes) },
      aws: { signQuery: true, allHeaders: true },
    });
    return { url: signed.url, headers };
  }

  async presignGet(key: string, expiresSeconds = 300): Promise<string> {
    const url = new URL(this.url(key));
    url.searchParams.set("X-Amz-Expires", String(expiresSeconds));
    // Served as a download of an opaque binary, never rendered inline.
    url.searchParams.set("response-content-type", "model/gltf-binary");
    url.searchParams.set("response-content-disposition", "attachment");
    const signed = await this.aws.sign(url.toString(), { method: "GET", aws: { signQuery: true } });
    return signed.url;
  }

  /** Size of the stored object, or null when it does not exist. */
  async headSize(key: string): Promise<number | null> {
    const res = await this.send(this.url(key), { method: "HEAD" });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`R2 HEAD failed: ${res.status}`);
    return Number(res.headers.get("content-length") ?? "NaN");
  }

  /** Bytes [start, end] inclusive. */
  async getRange(key: string, start: number, end: number): Promise<Uint8Array> {
    const res = await this.send(this.url(key), { method: "GET", headers: { Range: `bytes=${start}-${end}` } });
    if (!res.ok) throw new Error(`R2 ranged GET failed: ${res.status}`);
    return new Uint8Array(await res.arrayBuffer());
  }

  async delete(key: string): Promise<void> {
    const res = await this.send(this.url(key), { method: "DELETE" });
    if (!res.ok && res.status !== 404) throw new Error(`R2 DELETE failed: ${res.status}`);
  }

  /** Deletes every object under a prefix (account deletion). Returns how many were removed. */
  async deletePrefix(prefix: string): Promise<number> {
    let removed = 0;
    let token: string | null = null;
    do {
      const url = new URL(this.base);
      url.searchParams.set("list-type", "2");
      url.searchParams.set("prefix", prefix);
      if (token) url.searchParams.set("continuation-token", token);
      const res = await this.send(url.toString(), { method: "GET" });
      if (!res.ok) throw new Error(`R2 LIST failed: ${res.status}`);
      const xml = await res.text();
      const keys = [...xml.matchAll(/<Key>([^<]+)<\/Key>/g)].map((m) => decodeXml(m[1]));
      for (const key of keys) {
        await this.delete(key);
        removed++;
      }
      token = /<IsTruncated>true<\/IsTruncated>/.test(xml)
        ? (xml.match(/<NextContinuationToken>([^<]+)<\/NextContinuationToken>/)?.[1] ?? null)
        : null;
    } while (token);
    return removed;
  }

  private async send(url: string, init: RequestInit): Promise<Response> {
    const signed = await this.aws.sign(url, init);
    return this.fetchImpl(signed);
  }
}

function decodeXml(s: string): string {
  return s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
}
