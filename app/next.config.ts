import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // NEXT_DIST_DIR lets a check build or serve into its own folder (for example .next-verify), so it never
  // overwrites the .next folder of a dev server that is already running from this checkout.
  distDir: process.env.NEXT_DIST_DIR || '.next',
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
