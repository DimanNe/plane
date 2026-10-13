# syntax=docker/dockerfile:1.20
FROM node:22.22.0-bookworm-slim AS build
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH CI=1 TURBO_TELEMETRY_DISABLED=1
RUN npm install -g pnpm@11.10.0
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json .gitignore ./
# The dependencies are installed from the manifests alone, before any source is copied. node_modules is most of
# these images, and the live and space images are this whole stage: installed after the sources, it was a new
# layer at every change of a source file, and saving the image wrote and unpacked all of it again.
COPY --parents packages/*/package.json apps/web/package.json apps/admin/package.json apps/space/package.json apps/live/package.json ./
RUN --mount=type=cache,id=plane-runtime-pnpm,target=/pnpm/store pnpm install --frozen-lockfile --store-dir=/pnpm/store
COPY packages ./packages
COPY apps/web ./apps/web
COPY apps/admin ./apps/admin
COPY apps/space ./apps/space
COPY apps/live ./apps/live
ENV VITE_API_BASE_URL="" VITE_ADMIN_BASE_URL="" VITE_ADMIN_BASE_PATH=/god-mode VITE_SPACE_BASE_URL="" VITE_SPACE_BASE_PATH=/spaces VITE_LIVE_BASE_URL="" VITE_LIVE_BASE_PATH=/live VITE_WEB_BASE_URL=""
RUN pnpm turbo run build --filter=web --filter=admin --filter=space --filter=live
# As built, the live server and Spaces load a few thousand module files from node_modules at every
# start, and Node spends nearly all of the start on finding and compiling them. Each server is
# bundled into one file here. Left outside the bundles: react and react-router, which must exist
# once in a process and are also loaded by code that stays in node_modules; sharp, which ships a
# native binary; react-pdf, which finds its font files through its own package.json.
RUN npm install -g esbuild@0.28.1
COPY <<'BANNER' /app/esm-bundle-banner.js
import { createRequire as __createRequire } from "node:module";
import { fileURLToPath as __fileURLToPath } from "node:url";
import { dirname as __pathDirname } from "node:path";
const require = __createRequire(import.meta.url);
const __filename = __fileURLToPath(import.meta.url);
const __dirname = __pathDirname(__filename);
BANNER
RUN esbuild apps/live/dist/start.mjs --outfile=apps/live/dist/start.bundle.mjs \
        --bundle --platform=node --format=esm --target=node22 --log-level=error \
        --banner:js="$(cat /app/esm-bundle-banner.js)" \
        --external:react --external:sharp '--external:@react-pdf/*' \
    && esbuild apps/space/build/server/index.js --outfile=apps/space/build/server/index.bundle.js \
        --bundle --platform=node --format=esm --target=node22 --log-level=error \
        --banner:js="$(cat /app/esm-bundle-banner.js)" \
        --external:react --external:react-dom --external:react-router '--external:@react-router/*'
# Node would compile each bundle from source at every start. With this variable it keeps the
# compiled form in a directory and reuses it; loading each bundle once here fills that directory.
# The live server ends this run itself because it has no configuration yet, after its code was
# compiled, so the result is judged by the cache alone.
ENV NODE_COMPILE_CACHE=/app/.node-compile-cache
COPY <<'SCRIPT' /app/write-compile-cache.mjs
import { flushCompileCache } from "node:module";
await import(process.argv[2]);
flushCompileCache();
process.exit(0);
SCRIPT
RUN node write-compile-cache.mjs /app/apps/live/dist/start.bundle.mjs; \
    (cd apps/space && node /app/write-compile-cache.mjs /app/apps/space/build/server/index.bundle.js) \
    && test -n "$(ls -A /app/.node-compile-cache)"
FROM build AS live
ENV NODE_ENV=production
FROM build AS space
ENV NODE_ENV=production
WORKDIR /app/apps/space
FROM caddy:2.10.2-alpine AS proxy
COPY --from=build /app/apps/web/build/client /srv/web
COPY --from=build /app/apps/admin/build/client /srv/admin
