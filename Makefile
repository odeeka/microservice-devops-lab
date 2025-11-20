.PHONY: help build up down logs test clean lint format install dev prod

# Default target
help:
	@echo "Available commands:"
	@echo "  help      - Show this help message"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services without daemon"
	@echo "  upd       - Start all services with daemon"
	@echo "  down      - Stop all services"
	@echo "  logs      - Show logs from all services"
	@echo "  test      - Run tests"
	@echo "  clean     - Clean up Docker resources"
	@echo "  lint      - Run code linting"
	@echo "  format    - Format code"
	@echo "  install   - Install dependencies"
	@echo "  dev       - Start development environment"
	@echo "  prod      - Start production environment"

# Build Docker images
build:
	@echo "Building Docker images..."
	docker-compose -f docker/docker-compose.yaml build

# Start all services
up:
	@echo "Starting all services without daemon..."
	docker-compose -f docker/docker-compose.yaml up --build

upd:
	@echo "Starting all services with daemon..."
	docker-compose -f docker/docker-compose.yaml up -d --build

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose -f docker/docker-compose.yaml down

# Show logs
logs:
	@echo "Showing logs..."
	docker-compose -f docker/docker-compose.yaml logs -f

# Run tests
test:
	@echo "Running tests..."
	docker-compose -f docker/docker-compose.yaml exec api python -m pytest tests/ -v

# Clean up Docker resources
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose -f docker/docker-compose.yaml down -v --remove-orphans
	docker system prune -f

# Run code linting
lint:
	@echo "Running linting..."
	python -m flake8 app/ tests/
	python -m black --check app/ tests/
	python -m isort --check-only app/ tests/

# Format code
format:
	@echo "Formatting code..."
	python -m black app/ tests/
	python -m isort app/ tests/

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r app/requirements.txt
	pip install flake8 black isort

# Development environment
dev:
	@echo "Starting development environment..."
	cp .env.example .env
	docker-compose -f docker/docker-compose.yaml up --build

# Production environment
prod:
	@echo "Starting production environment..."
	cp .env .env
	docker-compose -f docker/docker-compose.yaml up -d --build

# Database migration (if using Alembic)
migrate:
	@echo "Running database migrations..."
	docker-compose -f docker/docker-compose.yaml exec api python -m alembic upgrade head

# Database seed
seed:
	@echo "Seeding database..."
	docker-compose -f docker/docker-compose.yaml exec api python -c "from app.db.seed import seed_database; seed_database()"

# Monitor services
monitor:
	@echo "Opening monitoring dashboards..."
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "API Docs: http://localhost:8000/docs"