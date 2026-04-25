/** @type {import('next').NextConfig} */
const backendProxy = process.env.BACKEND_PROXY_URL || "http://127.0.0.1:8000";

const nextConfig = {
    output: "standalone",
    optimizeFonts: false,
    /** Dev / local: proxy /api to FastAPI so the browser can use same-origin /api calls. */
    async rewrites() {
        return [
            // Match nginx: /api/socket.io -> FastAPI Socket.IO at /socket.io
            {
                source: "/api/socket.io/:path*",
                destination: `${backendProxy}/socket.io/:path*`,
            },
            {
                source: "/api/:path*",
                destination: `${backendProxy}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
