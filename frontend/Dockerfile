# --- Build stage: compile the Vite/React app ---
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Internal API token baked into the bundle (matches the api's INTERNAL_API_TOKEN).
ARG VITE_INTERNAL_TOKEN=
ENV VITE_INTERNAL_TOKEN=${VITE_INTERNAL_TOKEN}
RUN npm run build

# --- Serve stage: nginx serves the static build + proxies the API ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
