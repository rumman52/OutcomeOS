import type { NextConfig } from "next";

const production = process.env.APP_ENV === "production" || process.env.NODE_ENV === "production";
const unsafeDemoConfiguration =
  process.env.DEMO_AUTH_ENABLED === "true" || process.env.MOCK_INTEGRATIONS_ENABLED === "true";

if (production && unsafeDemoConfiguration) {
  throw new Error("Demo authentication and mock integrations are forbidden in production.");
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
