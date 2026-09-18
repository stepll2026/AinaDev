# Next.js 生产镜像
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# 自托管 vditor 静态资源到 public/vditor/dist（Vditor 按 cdn+"/dist/..." 拼路径加载，
# 整目录复制保证 i18n/lute/highlight/katex/icons/method.min.js 等全部本地可用，
# 不依赖外网 unpkg CDN；内网/受限网络环境必须本地化）
RUN mkdir -p public/vditor \
 && cp -r node_modules/vditor/dist public/vditor/dist \
 && find public/vditor -type f | wc -l
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
# public 静态资源（vditor 本地化资源等），next start 从 /app/public 提供
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
