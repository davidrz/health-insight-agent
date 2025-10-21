"""
Configuration management for Health Insight Agent
"""
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # Application settings
    APP_NAME: str = "Health Insight Agent"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    VERSION: str = "1.0.0"
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # Database settings
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/health_insight",
        description="Database connection URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Database max overflow connections")
    
    # Redis settings
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    REDIS_POOL_SIZE: int = Field(default=10, description="Redis connection pool size")
    CACHE_TTL: int = Field(default=3600, description="Default cache TTL in seconds")
    
    # AWS settings
    AWS_REGION: str = Field(default="us-east-1", description="AWS region")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS access key ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="AWS secret access key")
    
    # AWS Bedrock settings
    BEDROCK_MODEL_ID: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        description="Bedrock model ID for LLM operations"
    )
    BEDROCK_MAX_TOKENS: int = Field(default=4096, description="Maximum tokens for Bedrock responses")
    BEDROCK_TEMPERATURE: float = Field(default=0.1, description="Temperature for Bedrock model")
    
    # AWS SageMaker settings
    SAGEMAKER_ENDPOINT_NAME: Optional[str] = Field(
        default=None,
        description="SageMaker endpoint name for ML inference"
    )
    SAGEMAKER_INSTANCE_TYPE: str = Field(
        default="ml.t2.medium",
        description="SageMaker instance type"
    )
    
    # Security settings
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT tokens"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        description="API rate limit per minute per user"
    )
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    
    # Health check settings
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=30,
        description="Health check timeout in seconds"
    )
    
    # MCP Server settings
    MCP_SERVER_HOST: str = Field(default="localhost", description="MCP server host")
    MCP_SERVER_PORT: int = Field(default=8001, description="MCP server port")
    MCP_MAX_AGENTS: int = Field(default=10, description="Maximum number of registered agents")
    
    # Analysis settings
    ANALYSIS_TIMEOUT: int = Field(
        default=30,
        description="Maximum time for health analysis in seconds"
    )
    MAX_CONCURRENT_ANALYSES: int = Field(
        default=5,
        description="Maximum concurrent health analyses"
    )
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for migrations"""
        return self.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")


# Global settings instance
settings = Settings()