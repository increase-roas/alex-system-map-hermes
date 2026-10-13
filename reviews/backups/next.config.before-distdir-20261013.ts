import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  eslint: { ignoreDuringBuilds: true },
  productionBrowserSourceMaps: true,
  async redirects() {
    return [
      {
        source: '/',
        destination: '/explorer',
        permanent: false,
      },
      {
        source: '/workflow',
        destination: '/explorer',
        permanent: false,
      },
    ];
  },
  async rewrites() {
    return [
      { source: '/api/generate-text', destination: '/api/disabled-ai' },
      { source: '/api/generate-image', destination: '/api/disabled-ai' },
    ];
  },
};

export default nextConfig;
