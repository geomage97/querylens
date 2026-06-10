import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles a minimal node server for the Docker image
  output: "standalone",
};

export default nextConfig;
