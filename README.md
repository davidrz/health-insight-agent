# Health Insight Agent

AI-powered health analysis system that provides personalized health insights and recommendations using advanced machine learning models.

## 🚀 Features

- **AI Health Analysis**: Personalized health insights using AWS Bedrock
- **Clean Architecture**: Scalable and maintainable codebase
- **FastAPI Backend**: High-performance async API
- **MCP Integration**: Model Context Protocol for agent orchestration
- **Real-time Processing**: Efficient health data analysis

## 📋 Project Structure

```
health-insight-agent/
├── .kiro/specs/           # Project specifications and documentation
├── backend/               # FastAPI backend application
│   ├── app/
│   │   ├── api/          # API routes and schemas
│   │   ├── agents/       # AI agent orchestration
│   │   ├── services/     # Business logic services
│   │   ├── domain/       # Core business entities
│   │   ├── infra/        # Infrastructure implementations
│   │   └── core/         # Configuration and utilities
│   ├── requirements.txt  # Python dependencies
│   └── README.md        # Backend-specific documentation
└── README.md            # This file
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd health-insight-agent
   ```

2. **Set up the backend**
   ```bash
   # Create and activate virtual environment
   python3 -m venv backend/venv
   source backend/venv/bin/activate  # On Windows: backend\venv\Scripts\activate
   
   # Install dependencies
   pip install -r backend/requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Copy environment template
   cp backend/.env.example backend/.env
   
   # Edit backend/.env with your configuration
   ```

4. **Run the application**
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access the API**
   - API Documentation: http://127.0.0.1:8000/docs
   - Health Check: http://127.0.0.1:8000/api/v1/health

## 🧪 Testing

```bash
# Activate virtual environment
source backend/venv/bin/activate

# Run tests
cd backend
pytest

# Run with coverage
pytest --cov=app
```

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## 🔧 Development

### Code Quality

```bash
# Format code
black backend/app/

# Sort imports
isort backend/app/

# Lint code
flake8 backend/app/

# Run all quality checks
black backend/app/ && isort backend/app/ && flake8 backend/app/
```

### Project Specifications

This project follows a spec-driven development approach. All specifications are located in `.kiro/specs/health-insight-agent/`:

- `requirements.md` - Functional requirements
- `design.md` - System architecture and design
- `tasks.md` - Implementation tasks and progress

## 🚀 Deployment

### Environment Variables

Key environment variables (see `backend/.env.example`):

```bash
# Application
DEBUG=false
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/health_insight

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Redis
REDIS_URL=redis://localhost:6379/0
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues:

1. Check the [API documentation](http://127.0.0.1:8000/docs)
2. Review the project specifications in `.kiro/specs/`
3. Open an issue on GitHub

## 🔗 Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)