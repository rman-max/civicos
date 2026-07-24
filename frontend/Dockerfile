FROM node:22-alpine AS dependencies
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
COPY pnpm-workspace.yaml ./
COPY frontend/package.json ./frontend/package.json
RUN pnpm install --frozen-lockfile --filter @civicos/frontend...

FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_BETA_ANALYTICS_ENABLED=false
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_BETA_ANALYTICS_ENABLED=$NEXT_PUBLIC_BETA_ANALYTICS_ENABLED
COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=dependencies /app/frontend/node_modules ./frontend/node_modules
COPY . .
RUN pnpm --dir frontend build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./frontend/.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "frontend/server.js"]
