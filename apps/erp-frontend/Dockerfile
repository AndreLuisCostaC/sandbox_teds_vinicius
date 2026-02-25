FROM node:20-alpine AS deps
WORKDIR /app
COPY src/frontend-admin/package*.json ./
RUN npm ci

FROM deps AS dev
WORKDIR /app
COPY src/frontend-admin/ ./
EXPOSE 3001
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3001"]

FROM deps AS builder
WORKDIR /app
COPY src/frontend-admin/ ./
RUN npm run build

FROM node:20-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
USER nextjs
EXPOSE 3001
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3001"]
