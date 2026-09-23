/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disable font optimization to avoid build failures in restricted network environments
  optimizeFonts: false,
  images: {
    // Allow any remote images for the portfolio section in this prototype
    unoptimized: true,
  },
  eslint: {
    // Only run linting on local development, skip during Docker build if needed
    // However, it's better to fix the issues. For now, let's keep it enabled but robust.
  }
}

export default nextConfig
