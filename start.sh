#!/bin/bash

# Start script for local development

echo "🚀 Starting Minister Management Application..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Please edit .env file with your passwords before continuing."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose first."
    exit 1
fi

# Create data directory for database
mkdir -p data

echo "📦 Building and starting containers..."
docker-compose up --build

echo "✅ Application is running at http://localhost:8080"
echo "🛑 Press Ctrl+C to stop"
