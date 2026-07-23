FROM node:20-alpine

# Enable pnpm via Corepack
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

# Install dependencies (layer caching)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

EXPOSE 5173

CMD ["pnpm", "dev"]
