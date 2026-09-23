FROM node:20-alpine

# Set build arguments for Next.js environment variables
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

WORKDIR /app

# Copy dependency definitions
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies with resilience
RUN npm config set fetch-retries 5 && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm install --legacy-peer-deps

# Copy frontend source code
COPY frontend .

# Build the application
# We need the API URL at build time for client-side bundle
RUN npm run build

# Expose port and start
EXPOSE 3000
CMD ["npm", "run", "start"]
