FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html ./
COPY frontend/vite.config.js ./
COPY frontend/public ./public
COPY frontend/src ./src
ARG APP_VERSION
ARG GIT_COMMIT
RUN test -n "$APP_VERSION" && test -n "$GIT_COMMIT"
ENV VITE_RELEASE_BUILD=1 \
    VITE_APP_VERSION=${APP_VERSION} \
    VITE_GIT_COMMIT=${GIT_COMMIT}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deployment/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
