import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";
import { LEGAL_PLACEHOLDERS_ALLOWED } from "@/lib/legal";

const ROOT = join(import.meta.dirname, "..");
/** Everything a visitor can read without signing in, plus the components those pages are built from. */
const SCAN = ["app/(public)", "app/(marketing)", "app/(auth)", "components/trust", "components/landing", "components/layout", "lib/help.ts"];
const PLACEHOLDER = /\[(?:Owner|To be confirmed)[^\]]*\]|Draft\s+[—-]\s+pending owner review/g;

function files(path: string): string[] {
  const abs = join(ROOT, path);
  if (statSync(abs).isFile()) return [abs];
  return readdirSync(abs, { recursive: true, encoding: "utf8" })
    .map((f) => join(abs, f))
    .filter((f) => /\.(tsx?|md)$/.test(f) && !/\.test\.tsx?$/.test(f));
}

function placeholders(): string[] {
  const found: string[] = [];
  for (const file of SCAN.flatMap(files)) {
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => {
      for (const m of line.matchAll(PLACEHOLDER)) found.push(`${relative(ROOT, file).split(sep).join("/")}:${i + 1}  ${m[0]}`);
    });
  }
  return found;
}

describe("owner-pending legal placeholders", () => {
  it("finds the placeholders it is meant to guard (the scan is not silently empty)", () => {
    // A known positive: while the flag allows them, the drafts still contain some. Once the owner has filled
    // every one in, set LEGAL_PLACEHOLDERS_ALLOWED to false and this check stops applying.
    if (LEGAL_PLACEHOLDERS_ALLOWED) expect(placeholders().length).toBeGreaterThan(0);
  });

  it("ships none once LEGAL_PLACEHOLDERS_ALLOWED is false (lib/legal.ts, the owner's launch switch)", () => {
    if (LEGAL_PLACEHOLDERS_ALLOWED) return;
    const left = placeholders();
    expect(left, `Fill these in before launch:\n${left.join("\n")}`).toEqual([]);
  });
});
