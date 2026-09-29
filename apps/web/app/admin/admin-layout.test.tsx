import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import robots from "../robots";
import sitemap from "../sitemap";

const h = vi.hoisted(() => ({ admin: false }));
vi.mock("next/navigation", async (orig) => ({ ...(await orig<object>()), usePathname: () => "/admin" }));
vi.mock("@/lib/server/admin", () => ({
  requireAdmin: async () => (h.admin ? { user: { id: "x" } } : new Response(null, { status: 403 })),
}));

const { default: AdminLayout, metadata } = await import("./layout");

afterEach(() => {
  vi.unstubAllEnvs();
  h.admin = false;
});

describe("/admin", () => {
  it("is never indexed and never advertised", () => {
    expect(metadata.robots).toMatchObject({ index: false, follow: false });
    expect(sitemap().some((e) => e.url.includes("/admin"))).toBe(false);
    // Listing it in robots.txt would advertise it; the noindex header and meta do the job instead.
    expect(JSON.stringify(robots())).not.toContain("admin");
  });

  it("shows the live-backend notice in Local mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    render(await AdminLayout({ children: <p>secret console</p> }));
    expect(screen.getByRole("heading", { name: "Admin requires the live backend" })).toBeTruthy();
    expect(screen.queryByText("secret console")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Admin" })).toBeNull();
  });

  it("is a 404 for anyone who is not an admin", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    await expect(AdminLayout({ children: <p>secret console</p> })).rejects.toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("renders the console for an admin", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    h.admin = true;
    render(await AdminLayout({ children: <p>secret console</p> }));
    expect(screen.getByText("secret console")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Overview" }).getAttribute("aria-current")).toBe("page");
  });
});
