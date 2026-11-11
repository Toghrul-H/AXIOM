import type { NextConfig } from "next";

// One same-origin proxy, with no provider-specific services or CORS changes.
const apiUrl = process.env.API_BASE_URL;
if (!apiUrl)
  throw new Error(
    "Set API_BASE_URL in frontend/.env.local (see .env.example).",
  );
const parsed = new URL(apiUrl);
if (
  !["http:", "https:"].includes(parsed.protocol) ||
  parsed.username ||
  parsed.password ||
  parsed.search ||
  parsed.hash
) {
  throw new Error(
    "API_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment.",
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/student/:path*",
        destination: `${apiUrl.replace(/\/$/, "")}/student/:path*`,
      },
    ];
  },
};

export default nextConfig;
