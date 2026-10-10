################  BUILD  ################
FROM node:20-alpine AS builder
WORKDIR /app

# Імена мають збігатися з `args:` у docker-compose.yml І мати префікс VITE_ —
# Vite підставляє в збірку тільки змінні з цим префіксом. Раніше тут стояв
# `ARG API_URL`, а compose передавав `VITE_API_URL`: аргумент мовчки
# ігнорувався. Рятував лише запасний варіант у `src/config.js`, тож зламалося б
# це рівно тоді, коли комусь знадобиться інша адреса API.
ARG VITE_API_URL
ARG VITE_WS_URL

ENV VITE_API_URL=$VITE_API_URL \
    VITE_WS_URL=$VITE_WS_URL


COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .
RUN npm run build

################  RUNTIME  ################
FROM nginx:alpine
# прибираємо дефолт, щоб не зловити 403/404
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
