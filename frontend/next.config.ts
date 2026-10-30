import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image Docker minimale : seuls les fichiers nécessaires à l'exécution.
  output: "standalone",
  poweredByHeader: false,
  cacheComponents: true,
  partialPrefetching: true,
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
