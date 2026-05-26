/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [
      {
        source: '/images/:path*',
        destination: 'http://localhost:8001/images/:path*',
      },
    ]
  },
}
module.exports = nextConfig
