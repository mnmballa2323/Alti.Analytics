import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // OpenTelemetry instrumentation 
  experimental: {
    instrumentationHook: true,
  },
};

export default nextConfig;
