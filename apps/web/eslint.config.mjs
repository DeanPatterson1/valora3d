import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
      // lib/zod.ts turns zod's JIT off in the browser; a direct import can build a schema before that runs and
      // trips the CSP (no 'unsafe-eval' in production).
      "no-restricted-imports": ["error", { paths: [{ name: "zod", message: 'Import from "@/lib/zod" (CSP: jitless in the browser).' }] }],
    },
  },
  {
    files: ["lib/zod.ts"],
    rules: { "no-restricted-imports": "off" },
  },
  {
    // Specs take `test` from ./fixtures, which fails any test whose page saw a CSP violation.
    // Playwright fixtures call `use(...)`, which is not React's hook.
    files: ["e2e/**/*.ts"],
    rules: { "react-hooks/rules-of-hooks": "off" },
  },
  {
    files: ["e2e/**/*.spec.ts"],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [
          { name: "zod", message: 'Import from "@/lib/zod".' },
          { name: "@playwright/test", importNames: ["test"], message: 'Import test from "./fixtures" (CSP violation guard).' },
        ],
      }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated browser reports contain bundled vendor code, not application sources.
    "playwright-report/**",
    "test-results/**",
    // Cloudflare/OpenNext build output.
    ".open-next/**",
    ".wrangler/**",
  ]),
]);

export default eslintConfig;
