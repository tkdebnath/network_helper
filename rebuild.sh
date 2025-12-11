#!/bin/bash

# Stop and remove containers, networks, images, and volumes
echo "Stopping and removing containers..."
docker compose down

# Remove the specific image
echo "Removing image network_helper:latest..."
docker rmi network_helper:latest

# Remove the database directory
if [ -d "data" ]; then
    echo "Removing data directory..."
    rm -rf data
fi

# Rebuild and start the container
echo "Rebuilding and starting container..."
docker compose up -d --build

# Prune dangling images to keep system clean
echo "Pruning dangling images..."
docker image prune -f

echo "Done! App should be running at http://localhost:8000"
