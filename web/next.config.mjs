/** @type {import('next').NextConfig} */
const isPages = process.env.GITHUB_PAGES === "1";
const basePath = isPages ? "/driveguard" : "";

const nextConfig = {
  output: isPages ? "export" : "standalone",
  reactStrictMode: true,
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  ...(isPages
    ? {
        basePath,
        assetPrefix: `${basePath}/`,
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
