# Imagen del frontend para el ambiente de pruebas:
#   etapa 1 — build de la SPA con Vite
#   etapa 2 — nginx sirve los estáticos y reenvía /api al contenedor `api`
# Build: docker compose -f ../docker-compose.staging.yml build web

FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
