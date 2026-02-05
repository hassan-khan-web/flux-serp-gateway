FROM node:18-alpine

WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose Vite default port
EXPOSE 5173

# Host 0.0.0.0 is required for Docker networking
CMD ["npm", "run", "dev", "--", "--host"]
