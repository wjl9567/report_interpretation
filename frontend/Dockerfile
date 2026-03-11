# 报告AI解读系统 - 前端（多阶段构建）
# stage 1: build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com 2>/dev/null || npm ci

COPY . .
RUN npm run build

# stage 2: serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
