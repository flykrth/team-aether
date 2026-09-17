# Stage 1: Production bundle build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors and install clean dependencies
COPY package*.json ./
RUN npm ci

# Copy frontend source code and execute production build
COPY . .
RUN npm run build

# Stage 2: High-performance static serving & reverse proxy
FROM nginx:alpine

# Copy custom Nginx configuration template
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy production /dist artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
