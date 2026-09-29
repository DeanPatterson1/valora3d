import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CONFIRM_TYPES } from "@/lib/auth/emailLink";
import { AUTH_TEMPLATES } from "./authTemplates";

const SUPABASE = join(__dirname, "..", "..", "supabase");
const TEMPLATES = join(SUPABASE, "templates");
const config = readFileSync(join(SUPABASE, "config.toml"), "utf8");
// The link types /auth/confirm accepts (app/auth/confirm/route.ts parses links with this list).
const confirmTypes: readonly string[] = CONFIRM_TYPES;

if (process.env.WRITE_EMAIL_TEMPLATES === "1") {
  mkdirSync(TEMPLATES, { recursive: true });
  for (const t of AUTH_TEMPLATES) writeFileSync(join(TEMPLATES, t.file), t.html);
}

describe("Supabase auth email templates", () => {
  it("covers every flow the brief names", () => {
    const keys = AUTH_TEMPLATES.map((t) => t.key);
    for (const k of ["confirmation", "magic_link", "recovery", "email_change", "invite"]) expect(keys).toContain(k);
  });

  for (const t of AUTH_TEMPLATES) {
    describe(t.key, () => {
      it("the file on disk matches the generator", () => {
        const path = join(TEMPLATES, t.file);
        expect(existsSync(path), `${t.file} missing: run WRITE_EMAIL_TEMPLATES=1 npx vitest run lib/email`).toBe(true);
        expect(readFileSync(path, "utf8").replaceAll("\r\n", "\n")).toBe(t.html);
      });

      it("contains its Supabase variables", () => {
        for (const v of t.variables) expect(t.html).toContain(v);
      });

      it("uses only variables Supabase fills in", () => {
        const used = [...t.html.matchAll(/\{\{\s*\.(\w+)\s*\}\}/g)].map((m) => m[1]);
        const allowed = ["ConfirmationURL", "Token", "TokenHash", "SiteURL", "Email", "NewEmail", "Data", "RedirectTo"];
        for (const v of used) expect(allowed).toContain(v);
        // Reauthentication has no link variables (Supabase docs: Token, SiteURL, Email, Data only).
        if (t.key === "reauthentication") expect(used.every((v) => ["Token", "SiteURL", "Email", "Data"].includes(v))).toBe(true);
        if (t.group === "notification") expect(used).toEqual([]);
      });

      it("links through /auth/confirm with a type the route accepts", () => {
        for (const m of t.html.matchAll(/\/auth\/confirm\?token_hash=\{\{ \.TokenHash \}\}&type=(\w+)&next=(\/[\w-]*)/g)) {
          expect(confirmTypes).toContain(m[1]);
        }
        if (t.variables.includes("{{ .TokenHash }}")) expect(t.html).toMatch(/\/auth\/confirm\?token_hash=/);
      });

      it("is mail-client safe: tables, no scripts, no external images, a plain-text link", () => {
        expect(t.html).toContain('role="presentation"');
        expect(t.html).not.toMatch(/<script/i);
        // The only <img> is the commented-out logo placeholder.
        expect(t.html.replace(/<!--[\s\S]*?-->/g, "")).not.toMatch(/<img/i);
        expect(t.html).toContain("prefers-color-scheme: dark");
        if (/v-btn-a" href="([^"]+)"/.test(t.html)) {
          const href = t.html.match(/v-btn-a" href="([^"]+)"/)![1];
          expect(t.html).toContain(`break-all;">${href}</a>`);
        }
      });

      it("is wired in config.toml", () => {
        const section = `[auth.email.${t.group}.${t.key}]`;
        const at = config.indexOf(section);
        expect(at, section).toBeGreaterThanOrEqual(0);
        const block = config.slice(at, at + 400);
        expect(block).toContain(`subject = "${t.subject}"`);
        expect(block).toContain(`content_path = "./templates/${t.file}"`);
      });
    });
  }
});
