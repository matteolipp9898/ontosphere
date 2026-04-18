FROM node:20-alpine

WORKDIR /app

# Copy dependency manifests and install
COPY package.json package-lock.json ./
RUN npm install

# Copy application source
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
