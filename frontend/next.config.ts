import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // Rewrites run on the Next.js server, so prefer API_URL (docker network)
        destination: `${process.env.API_URL || 'http://api:5537'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
