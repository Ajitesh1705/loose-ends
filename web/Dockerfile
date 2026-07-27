FROM node:22-slim

WORKDIR /app

# Install deps first so the image's node_modules populates the anon volume.
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
