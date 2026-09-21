# CariCue web image: builds the SPA, then serves it from Nginx and reverse
# proxies /api to the backend so the browser only ever sees one origin (which
# is what makes session cookies and CSRF work without CORS).
#
# Built with the repository root as the context, because the Nginx config it
# ships lives in deploy/:
#   docker build -f frontend/Dockerfile .

# --- build ---------------------------------------------------------------- #
FROM node:22-alpine AS build

WORKDIR /app

# Manifests first, so dependency installation is cached independently of
# source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- serve ---------------------------------------------------------------- #
FROM nginx:1.27-alpine AS serve

RUN apk add --no-cache curl

COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx/caricue.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
