# 多阶段构建
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# ==================== 运行时：nginx 静态托管 ====================
FROM nginx:1.27-alpine AS runtime

# 去掉默认配置
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
