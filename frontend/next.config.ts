import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Backend origin (for connect-src) derived from the build-time API URL, plus its
// WebSocket origin for the /voice stream.
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const WS_ORIGIN = API_ORIGIN.replace(/^http/, "ws");

// Hosts that legitimately serve images rendered in chat / avatars:
// Drive file icons, Google user pictures, and GCS-hosted generated images.
// Plus the news page's article thumbnails (fixed newspaper CDNs).
const IMG_HOSTS = [
  "https://drive-thirdparty.googleusercontent.com",
  "https://*.googleusercontent.com",
  "https://lh3.googleusercontent.com",
  "https://storage.googleapis.com",
  "https://media.eitb.eus",
  "https://*.epimg.net",
  "https://imagenes.elpais.com",
  "https://*.uecdn.es",
  "https://*.ppllstatics.com",
];

// The chat renders model-generated Markdown and remote images, so the token in
// localStorage is an XSS-exfiltration target. This CSP constrains where content
// can be loaded from and — critically — where data can be sent (connect-src)
// and images fetched (img-src), which are the practical exfiltration channels.
// script-src stays permissive (Next.js App Router hydration needs inline/eval);
// a nonce-based lockdown is tracked as a follow-up.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${IMG_HOSTS.join(" ")}`,
  "font-src 'self' data:",
  `connect-src 'self' ${API_ORIGIN} ${WS_ORIGIN}`,
  "media-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "drive-thirdparty.googleusercontent.com" },
      { protocol: "https", hostname: "*.googleusercontent.com" },
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      { protocol: "https", hostname: "storage.googleapis.com" },
    ],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=(self)" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
