import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: [...configDefaults.exclude, "e2e/**", ".next/**"],
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: { alias: { "@": import.meta.dirname } },
});
