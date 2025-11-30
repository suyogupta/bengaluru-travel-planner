FROM node:20-slim AS backend-builder
RUN apt-get update -y && apt-get install -y openssl
# Build backend step
WORKDIR /usr/src/app
COPY .env* ./

COPY package*.json ./
COPY smart-contracts ./smart-contracts
COPY ./src ./src
COPY ./prisma ./prisma
COPY ./public ./public
COPY tsconfig.json .
COPY eslint.config.mjs .

RUN npm install
RUN npx prisma generate
RUN npm run build
RUN npm run swagger-json

#RUN npm run prisma:migrate

# Frontend build step
FROM node:20-slim AS frontend-builder
WORKDIR /usr/src/app/frontend
COPY frontend/package*.json ./
COPY frontend/openapi-ts.config.ts ./openapi-ts.config.ts
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/.env* ./
COPY frontend/next.config.ts ./
COPY frontend/tailwind.config.ts ./
COPY frontend/postcss.config.mjs ./
COPY frontend/tsconfig.json ./
COPY frontend/components.json ./
COPY --from=backend-builder /usr/src/app/src/utils/generator/swagger-generator/openapi-docs.json ./openapi-docs.json

RUN npm install
RUN npm run openapi-ts
RUN npm run build


# Final stage
FROM node:20-slim AS runner
RUN apt-get update -y && apt-get install -y openssl
WORKDIR /usr/src/app

# Copy backend files
COPY --from=backend-builder /usr/src/app/dist ./dist
COPY --from=backend-builder /usr/src/app/node_modules ./node_modules
COPY --from=backend-builder /usr/src/app/package*.json ./
COPY --from=backend-builder /usr/src/app/prisma ./prisma
COPY --from=backend-builder /usr/src/app/smart-contracts ./smart-contracts
COPY --from=backend-builder /usr/src/app/src ./src
COPY --from=backend-builder /usr/src/app/public ./public
COPY --from=backend-builder /usr/src/app/tsconfig.json ./tsconfig.json
COPY --from=backend-builder /usr/src/app/eslint.config.mjs ./eslint.config.mjs

# Copy frontend files
COPY --from=frontend-builder /usr/src/app/frontend/dist ./frontend/dist

#optional copy env file
COPY .env* ./


EXPOSE 3001
ENV NODE_ENV=production
CMD [ "npm", "run", "start" ]
