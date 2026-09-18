import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ACCENT_HEX } from "./palette";

describe("viewer palette mirrors globals.css", () => {
  it("ACCENT_HEX equals --color-accent", () => {
    const css = readFileSync(join(import.meta.dirname, "../../app/globals.css"), "utf8");
    const m = css.match(/--color-accent:\s*([^;]+);/);
    if (!m) throw new Error("--color-accent not found in globals.css");
    expect(m[1].trim()).toBe(ACCENT_HEX);
  });
});
