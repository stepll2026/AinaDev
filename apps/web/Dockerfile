# Next.js 生产镜像
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# 自托管 vditor 静态资源到 public/vditor（Vditor 运行时按 cdn 从本站加载，
# 不依赖外网 unpkg CDN；内网/受限网络环境必须本地化）
RUN mkdir -p public/vditor/js/i18n public/vditor/js/icons public/vditor/js/lute public/vditor/js/highlight.js public/vditor/js/katex public/vditor/css/content-theme \
 && cp -r node_modules/vditor/dist/images public/vditor/images \
 && cp node_modules/vditor/dist/js/i18n/*.js public/vditor/js/i18n/ \
 && cp node_modules/vditor/dist/js/icons/*.js public/vditor/js/icons/ \
 && cp node_modules/vditor/dist/js/lute/lute.min.js public/vditor/js/lute/ \
 && cp node_modules/vditor/dist/js/highlight.js/highlight.min.js public/vditor/js/highlight.js/ \
 && cp -r node_modules/vditor/dist/js/highlight.js/styles public/vditor/js/highlight.js/styles \
 && cp node_modules/vditor/dist/js/katex/katex.min.js node_modules/vditor/dist/js/katex/katex.min.css public/vditor/js/katex/ \
 && cp -r node_modules/vditor/dist/js/katex/fonts public/vditor/js/katex/fonts \
 && cp node_modules/vditor/dist/css/content-theme/light.css node_modules/vditor/dist/css/content-theme/dark.css public/vditor/css/content-theme/ \
 && cp node_modules/vditor/dist/index.css public/vditor/ \
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
