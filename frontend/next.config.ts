import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image Docker minimale : seuls les fichiers nécessaires à l'exécution.
  output: "standalone",
  poweredByHeader: false,
  cacheComponents: true,
  partialPrefetching: true,
  // L'API est servie sous /api sur la même origine que le site : cookie de session
  // limité au domaine du site, pas de CORS. Adresse lue au build (argument Docker).
  async rewrites() {
    const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:18000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
