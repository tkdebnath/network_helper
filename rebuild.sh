#!/bin/bash

# Stop and remove containers, networks, images, and volumes
echo "Stopping and removing containers..."
docker compose down

# Remove the specific image
echo "Removing image network_helper:latest..."
docker rmi network_helper:latest

# Remove the database file
if [ -f "database.db" ]; then
    echo "Removing database.db..."
    rm -f database.db
fi

# Rebuild and start the container
echo "Rebuilding and starting container..."
docker compose up -d --build

echo "Done! App should be running at http://localhost:8000"
