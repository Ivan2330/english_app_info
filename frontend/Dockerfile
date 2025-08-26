################  BUILD  ################
FROM node:20-alpine AS builder
WORKDIR /app

ARG API_URL

ENV API_URL=$API_URL


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
