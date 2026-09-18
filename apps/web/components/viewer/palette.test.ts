import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { PATH_HEX } from "./palette";

describe("viewer palette mirrors globals.css", () => {
  it("PATH_HEX equals --color-primary", () => {
    const css = readFileSync(join(import.meta.dirname, "../../app/globals.css"), "utf8");
    const m = css.match(/--color-primary:\s*([^;]+);/);
    if (!m) throw new Error("--color-primary not found in globals.css");
    expect(m[1].trim()).toBe(PATH_HEX);
  });
});
