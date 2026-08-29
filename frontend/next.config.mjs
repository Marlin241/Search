/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle so the Docker image can run
  // `node server.js` without node_modules (see Dockerfile).
  output: "standalone",
  // Local dev proxy: the browser calls /api/* (same origin) and Next
  // forwards to the backend. In the Docker image NEXT_PUBLIC_API_URL is
  // baked at build time instead (see lib/api.ts), so this rewrite is only
  // exercised by `npm run dev`.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
