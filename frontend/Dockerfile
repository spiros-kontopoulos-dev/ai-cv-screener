# Use a lightweight Node.js 22 image for the React/Vite development server.
FROM node:22-alpine

# All following commands run from /app inside the container.
WORKDIR /app

# Copy dependency files first.
# Docker can reuse the dependency-installation layer when application code
# changes but package.json and package-lock.json remain unchanged.
COPY package.json package-lock.json ./

# Install the exact dependency versions recorded in package-lock.json.
RUN npm ci

# Copy the React, TypeScript, and Vite source files into the image.
COPY . .

# Vite's default development port.
EXPOSE 5173

# --host 0.0.0.0 makes Vite reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]