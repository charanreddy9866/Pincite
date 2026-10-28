import type { NextConfig } from "next";

// Exported as static files and served by the FastAPI app, so the whole product is one container.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
