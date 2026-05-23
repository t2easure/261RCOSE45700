/** @type {import('next').NextConfig} */
const nextConfig = {
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
