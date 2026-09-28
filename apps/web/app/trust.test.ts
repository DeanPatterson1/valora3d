import { afterEach, describe, expect, it, vi } from "vitest";
import DevLayout from "./(app)/dev/layout";
import robots from "./robots";
import sitemap from "./sitemap";
import { publicMetadata } from "@/lib/site";

afterEach(() => vi.unstubAllEnvs());

describe("public route policy", () => {
  it("rejects dev pages on the server in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(() => DevLayout({ children: "private development tools" })).toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("keeps development tools available outside production", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(DevLayout({ children: "development tools" })).toBe("development tools");
  });

  it("excludes account and dev routes from discovery", () => {
    const urls = sitemap().map((entry) => entry.url);
    expect(urls).toHaveLength(16);
    expect(urls).toContain("https://valora3d.com/pricing");
    expect(urls.every((url) => !/\/(dev|projects|settings|profile|login|signup)(\/|$)/.test(url))).toBe(true);
    expect(robots().sitemap).toBe("https://valora3d.com/sitemap.xml");
  });

  it("keeps social copy and canonical URLs specific to each page", () => {
    expect(publicMetadata("Contact", "Reach the owner", "/contact")).toMatchObject({
      title: "Contact", description: "Reach the owner",
      alternates: { canonical: "/contact" },
      openGraph: { title: "Contact", description: "Reach the owner", url: "/contact" },
    });
  });
});
