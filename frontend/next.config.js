/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [
      {
        source: '/images/:path*',
        destination: 'http://13.223.75.247:8001/images/:path*',
      },
    ]
  },
}
module.exports = nextConfig
