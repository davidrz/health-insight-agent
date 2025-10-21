# Health Insight Agent - Development Commands

.PHONY: help install dev test lint format clean

# Default target
help:
	@echo "Available commands:"
	@echo "  install    - Set up development environment"
	@echo "  dev        - Start development server"
	@echo "  test       - Run tests"
	@echo "  lint       - Run linting"
	@echo "  format     - Format code"
	@echo "  clean      - Clean temporary files"
	@echo "  check      - Run all quality checks"

# Set up development environment
install:
	python3 -m venv backend/venv
	backend/venv/bin/pip install --upgrade pip
	backend/venv/bin/pip install -r backend/requirements.txt
	@echo "✅ Development environment ready!"
	@echo "Activate with: source backend/venv/bin/activate"

# Start development server
dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	cd backend && python -m pytest

# Run tests with coverage
test-cov:
	cd backend && python -m pytest --cov=app --cov-report=html

# Run linting
lint:
	cd backend && flake8 app/

# Format code
format:
	cd backend && black app/
	cd backend && isort app/

# Run all quality checks
check: format lint test
	@echo "✅ All quality checks passed!"

# Clean temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

# Validate project structure
validate:
	@echo "🔍 Validating project structure..."
	@test -f backend/app/main.py || (echo "❌ Missing main.py" && exit 1)
	@test -f backend/app/core/config.py || (echo "❌ Missing config.py" && exit 1)
	@test -f backend/requirements.txt || (echo "❌ Missing requirements.txt" && exit 1)
	@echo "✅ Project structure is valid!"

# Quick health check
health:
	@echo "🏥 Running health check..."
	@curl -s http://127.0.0.1:8000/api/v1/health || echo "❌ Server not running"