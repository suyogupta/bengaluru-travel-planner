import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'dist',
  basePath: '/admin',
  env: {
    NEXT_PUBLIC_PAYMENT_API_BASE_URL:
      process.env.NEXT_PUBLIC_PAYMENT_API_BASE_URL || '/api/v1',
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
