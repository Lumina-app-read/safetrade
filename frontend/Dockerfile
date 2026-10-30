FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:20-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Adresse interne de l'API, figée dans les réécritures /api au moment du build.
ARG API_INTERNAL_URL=http://backend:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S -g 10001 safetrade && adduser -S -u 10001 -G safetrade safetrade
COPY --from=build --chown=safetrade:safetrade /app/.next/standalone ./
COPY --from=build --chown=safetrade:safetrade /app/.next/static ./.next/static
COPY --from=build --chown=safetrade:safetrade /app/public ./public
USER safetrade
EXPOSE 3000
CMD ["node", "server.js"]
