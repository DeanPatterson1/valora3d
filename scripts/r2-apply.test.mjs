import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { plan } from "./r2-apply.mjs";

const read = (name) => JSON.parse(readFileSync(new URL(`../infra/r2/${name}`, import.meta.url), "utf8"));
const base = { uploads: "up", backups: "bk", corsFile: "c.json", corsFileWithLocalhost: "cl.json" };

test("cors allows PUT with If-None-Match from the production origins only", () => {
  const [rule] = read("uploads.cors.json").rules;
  assert.deepEqual(rule.allowed.origins, ["https://valora3d.com", "https://www.valora3d.com"]);
  assert.ok(rule.allowed.methods.includes("PUT") && rule.allowed.methods.includes("GET"));
  assert.ok(rule.allowed.headers.includes("if-none-match"));
  assert.ok(!rule.allowed.methods.includes("DELETE"));
});

test("lifecycle aborts incomplete multipart uploads after one day and expires nothing", () => {
  for (const name of ["uploads.lifecycle.json", "backups.lifecycle.json"]) {
    const { rules } = read(name);
    assert.equal(rules.length, 1);
    assert.equal(rules[0].abortMultipartUploadsTransition.condition.maxAge, 86400);
    assert.equal(rules[0].deleteObjectsTransition, undefined, `${name} must not delete objects`);
  }
});

test("plan: both buckets, in order, with the shared files", () => {
  const steps = plan(base);
  assert.deepEqual(steps.map((s) => s.args.slice(0, 4).join(" ")), ["r2 bucket cors set", "r2 bucket lifecycle set", "r2 bucket lifecycle set"]);
  assert.equal(steps[0].args[4], "up");
  assert.equal(steps[2].args[4], "bk");
});

test("plan: --only, localhost origins and the optional lock", () => {
  assert.equal(plan({ ...base, only: "backups" }).length, 1);
  assert.equal(plan({ ...base, only: "uploads" }).length, 2);
  assert.ok(plan({ ...base, includeLocalhost: true })[0].args.includes("cl.json"));
  assert.equal(plan({ ...base, lockBackups: true }).at(-1).args[2], "lock");
  assert.equal(plan({ ...base, only: "uploads", lockBackups: true }).some((s) => s.args[2] === "lock"), false);
});
