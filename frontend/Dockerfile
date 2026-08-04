FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# 端口由 VITE_PORT 控制（默认 5173，见 vite.config.ts / docker-compose.yml）
EXPOSE 5173

CMD ["sh", "-c", "npm run dev -- --host 0.0.0.0 --port ${VITE_PORT:-5173}"]
