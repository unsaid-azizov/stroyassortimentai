import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // Rewrites run on the Next.js server, so prefer AI_SERVICE_URL (docker network)
        destination: `${process.env.AI_SERVICE_URL || 'http://ai_service:5537'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
