/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    // 백엔드가 서빙하는 캡쳐 이미지를 next/image로 쓸 경우 대비 (현재는 일반 img 사용)
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000", pathname: "/media/**" },
    ],
  },
};

module.exports = nextConfig;
