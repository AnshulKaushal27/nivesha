# Frontend Dockerfile — Next.js Application

FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build the Next.js application
RUN npm run build

# Expose port
EXPOSE 3000

# Set environment for production
ENV NODE_ENV=production

# Run the application
CMD ["npm", "start"]
