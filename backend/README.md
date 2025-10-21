# Health Insight Agent Backend

AI-powered health analysis system built with FastAPI and Clean Architecture principles.

## Project Structure

```
backend/
├── app/
│   ├── api/           # API layer - FastAPI routes and schemas
│   ├── agents/        # Agents layer - AI agent orchestration and MCP server
│   ├── services/      # Services layer - Application services and use cases
│   ├── domain/        # Domain layer - Core business entities and repository interfaces
│   ├── infra/         # Infrastructure layer - Database, external services, and implementations
│   └── core/          # Core layer - Configuration, logging, and shared utilities
├── requirements.txt   # Python dependencies
├── .env.example      # Environment variables example
└── main.py           # FastAPI application entry point
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the application:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Health Check

Test the API with:
```bash
curl http://localhost:8000/api/v1/health
```