FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM caddy:2.10-alpine
COPY deploy/playground.Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
