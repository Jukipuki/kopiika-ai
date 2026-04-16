import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// Read the repo-root VERSION file at build time so the client bundle can
// display whatever version is canonically shipped. Falls back to a recognizable
// marker if the file is missing (e.g. in a detached frontend-only build)
// rather than failing the build.
function readAppVersion(): string {
  try {
    return readFileSync(resolve(__dirname, "../VERSION"), "utf8").trim();
  } catch {
    return "0.0.0+dev";
  }
}

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_APP_VERSION: readAppVersion(),
  },
};

export default withNextIntl(nextConfig);
