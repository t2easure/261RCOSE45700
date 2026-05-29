/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [
      {
        source: '/images/:path*',
        destination: 'http://107.22.8.250:8001/images/:path*',
      },
    ]
  },
}
module.exports = nextConfig
