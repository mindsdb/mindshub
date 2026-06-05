FROM node:22-slim AS builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build:web

FROM nginx:alpine AS runtime

LABEL org.opencontainers.image.title="cowork-web"
LABEL org.opencontainers.image.source="https://github.com/mindsdb/minds-platform"

COPY --from=builder /build/dist/renderer-web/ /usr/share/nginx/html/
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
