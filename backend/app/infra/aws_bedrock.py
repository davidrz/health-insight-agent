"""
AWS Bedrock client for LLM operations in Health Insight Agent.

This module provides a client interface for AWS Bedrock services,
including natural language generation and symptom analysis capabilities.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from ..core.config import settings

logger = logging.getLogger(__name__)


class BedrockServiceError(Exception):
    """Base exception for Bedrock service errors."""
    pass


class BedrockRateLimitError(BedrockServiceError):
    """Raised when Bedrock service rate limit is exceeded."""
    pass


class BedrockModelError(BedrockServiceError):
    """Raised when Bedrock model inference fails."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for external service resilience."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution."""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class BedrockClient:
    """AWS Bedrock service client for LLM operations."""
    
    def __init__(self):
        self.region = settings.AWS_REGION
        self.model_id = settings.BEDROCK_MODEL_ID
        self.max_tokens = settings.BEDROCK_MAX_TOKENS
        self.temperature = settings.BEDROCK_TEMPERATURE
        
        # Configure boto3 client with retry logic
        config = Config(
            region_name=self.region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        self.client = boto3.client(
            'bedrock-runtime',
            config=config,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Circuit breaker for resilience
        self.circuit_breaker = CircuitBreaker()
        
        logger.info(f"Bedrock client initialized for region {self.region}")
    
    async def _invoke_model_with_retry(self, body: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Invoke Bedrock model with retry logic and circuit breaker.
        
        Args:
            body: Request body for the model
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict containing the model response
            
        Raises:
            BedrockServiceError: When service is unavailable or rate limited
            BedrockModelError: When model inference fails
        """
        if not self.circuit_breaker.can_execute():
            raise BedrockServiceError("Circuit breaker is OPEN - service unavailable")
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Convert to async call using asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.invoke_model(
                        modelId=self.model_id,
                        body=json.dumps(body),
                        contentType='application/json',
                        accept='application/json'
                    )
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                
                # Record success for circuit breaker
                self.circuit_breaker.record_success()
                
                logger.debug(f"Bedrock model invoked successfully on attempt {attempt + 1}")
                return response_body
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ThrottlingException':
                    last_exception = BedrockRateLimitError(f"Rate limit exceeded: {e}")
                    # Exponential backoff for rate limiting
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) * 1
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        continue
                elif error_code in ['ValidationException', 'ModelNotReadyException']:
                    last_exception = BedrockModelError(f"Model error: {e}")
                    break  # Don't retry for these errors
                else:
                    last_exception = BedrockServiceError(f"AWS service error: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(1)  # Brief wait before retry
                        continue
                        
            except BotoCoreError as e:
                last_exception = BedrockServiceError(f"Boto3 error: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                    
            except Exception as e:
                last_exception = BedrockServiceError(f"Unexpected error: {e}")
                break
        
        # Record failure for circuit breaker
        self.circuit_breaker.record_failure()
        
        logger.error(f"Bedrock model invocation failed after {max_retries + 1} attempts")
        raise last_exception
    
    async def generate_insights(self, prompt: str, context: Dict[str, Any]) -> str:
        """
        Generate natural language health insights using Bedrock LLM.
        
        Args:
            prompt: The prompt for insight generation
            context: Additional context data for the analysis
            
        Returns:
            str: Generated health insights
            
        Raises:
            BedrockServiceError: When service call fails
        """
        try:
            # Construct the full prompt with context
            full_prompt = self._build_insight_prompt(prompt, context)
            
            # Prepare request body for Claude model
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ]
            }
            
            logger.info("Generating health insights with Bedrock")
            response = await self._invoke_model_with_retry(body)
            
            # Extract content from Claude response
            if 'content' in response and len(response['content']) > 0:
                insights = response['content'][0]['text']
                logger.info("Health insights generated successfully")
                return insights
            else:
                raise BedrockModelError("Invalid response format from Bedrock model")
                
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            raise
    
    async def analyze_symptoms(self, symptoms: List[str]) -> Dict[str, Any]:
        """
        Analyze symptoms using Bedrock LLM for medical assessment.
        
        Args:
            symptoms: List of symptom descriptions
            
        Returns:
            Dict containing symptom analysis results
            
        Raises:
            BedrockServiceError: When service call fails
        """
        try:
            # Build symptom analysis prompt
            prompt = self._build_symptom_analysis_prompt(symptoms)
            
            # Prepare request body
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": 0.1,  # Lower temperature for medical analysis
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            logger.info(f"Analyzing {len(symptoms)} symptoms with Bedrock")
            response = await self._invoke_model_with_retry(body)
            
            # Extract and parse analysis
            if 'content' in response and len(response['content']) > 0:
                analysis_text = response['content'][0]['text']
                
                # Parse structured analysis from response
                analysis = self._parse_symptom_analysis(analysis_text)
                
                logger.info("Symptom analysis completed successfully")
                return analysis
            else:
                raise BedrockModelError("Invalid response format from Bedrock model")
                
        except Exception as e:
            logger.error(f"Failed to analyze symptoms: {e}")
            raise
    
    def _build_insight_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """Build a comprehensive prompt for health insight generation."""
        context_str = json.dumps(context, indent=2) if context else "No additional context provided"
        
        return f"""
You are a medical AI assistant specializing in health data analysis. 
Generate personalized health insights based on the provided data and context.

User Request: {prompt}

Health Data Context:
{context_str}

Please provide:
1. Key health observations
2. Potential risk factors
3. Personalized recommendations
4. Areas requiring attention

Ensure your response is:
- Evidence-based and medically sound
- Personalized to the individual's data
- Clear and actionable
- Appropriately cautious about medical advice

Response should be in a clear, structured format.
"""
    
    def _build_symptom_analysis_prompt(self, symptoms: List[str]) -> str:
        """Build a prompt for symptom analysis."""
        symptoms_str = "\n".join([f"- {symptom}" for symptom in symptoms])
        
        return f"""
You are a medical AI assistant. Analyze the following symptoms and provide a structured assessment.

Reported Symptoms:
{symptoms_str}

Please provide a JSON-formatted analysis with the following structure:
{{
    "severity_assessment": "low|moderate|high",
    "potential_conditions": ["condition1", "condition2"],
    "recommended_actions": ["action1", "action2"],
    "urgency_level": "routine|urgent|emergency",
    "additional_questions": ["question1", "question2"],
    "confidence_score": 0.0-1.0
}}

Focus on:
1. Symptom severity and urgency
2. Possible underlying conditions
3. Recommended next steps
4. Questions for further assessment

Be conservative and recommend professional medical consultation when appropriate.
"""
    
    def _parse_symptom_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse structured symptom analysis from LLM response."""
        try:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            
            if json_match:
                analysis_json = json.loads(json_match.group())
                return analysis_json
            else:
                # Fallback to text-based parsing
                return {
                    "severity_assessment": "moderate",
                    "potential_conditions": [],
                    "recommended_actions": ["Consult healthcare provider"],
                    "urgency_level": "routine",
                    "additional_questions": [],
                    "confidence_score": 0.5,
                    "raw_analysis": analysis_text
                }
                
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse symptom analysis JSON: {e}")
            return {
                "severity_assessment": "moderate",
                "potential_conditions": [],
                "recommended_actions": ["Consult healthcare provider"],
                "urgency_level": "routine",
                "additional_questions": [],
                "confidence_score": 0.5,
                "raw_analysis": analysis_text,
                "parse_error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Bedrock service.
        
        Returns:
            Dict containing health check results
        """
        try:
            # Simple test call to verify service availability
            test_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 10,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello"
                    }
                ]
            }
            
            await self._invoke_model_with_retry(test_body)
            
            return {
                "status": "healthy",
                "service": "bedrock",
                "model_id": self.model_id,
                "region": self.region,
                "circuit_breaker_state": self.circuit_breaker.state,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "bedrock",
                "error": str(e),
                "circuit_breaker_state": self.circuit_breaker.state,
                "timestamp": datetime.now().isoformat()
            }


# Global Bedrock client instance
_bedrock_client: Optional[BedrockClient] = None


def get_bedrock_client() -> BedrockClient:
    """Get or create the global Bedrock client instance."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client


async def init_bedrock() -> bool:
    """Initialize Bedrock client and verify connectivity."""
    try:
        client = get_bedrock_client()
        health_result = await client.health_check()
        
        if health_result["status"] == "healthy":
            logger.info("Bedrock client initialized successfully")
            return True
        else:
            logger.error(f"Bedrock health check failed: {health_result}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {e}")
        return False


async def close_bedrock() -> None:
    """Close Bedrock client connections."""
    global _bedrock_client
    if _bedrock_client:
        logger.info("Bedrock client connections closed")
        _bedrock_client = None