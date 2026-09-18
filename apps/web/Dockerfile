# Next.js 生产镜像
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# public 目录可能为空（favicon 由 app/ 提供），确保存在以便 COPY 到运行镜像
RUN mkdir -p public
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
# public 静态资源（favicon 等），next start 从 /app/public 提供
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
