"""
AWS SageMaker client for ML model inference in Health Insight Agent.

This module provides a client interface for AWS SageMaker services,
including risk prediction and anomaly detection capabilities.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import numpy as np
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from ..core.config import settings

logger = logging.getLogger(__name__)


from app.core.exceptions import ExternalServiceError

class SageMakerServiceError(ExternalServiceError):
    """Base exception for SageMaker service errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service_name="AWS SageMaker", **kwargs)


class SageMakerEndpointError(SageMakerServiceError):
    """Raised when SageMaker endpoint is unavailable or fails."""
    pass


class SageMakerModelError(SageMakerServiceError):
    """Raised when SageMaker model inference fails."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for SageMaker service resilience."""
    
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


class HealthMetrics:
    """Data class for health metrics used in ML predictions."""
    
    def __init__(self, data: Dict[str, Any]):
        self.age = data.get('age', 0)
        self.gender = data.get('gender', 'unknown')
        self.heart_rate = data.get('heart_rate', 0)
        self.blood_pressure_systolic = data.get('blood_pressure_systolic', 0)
        self.blood_pressure_diastolic = data.get('blood_pressure_diastolic', 0)
        self.cholesterol = data.get('cholesterol', 0)
        self.glucose = data.get('glucose', 0)
        self.bmi = data.get('bmi', 0)
        self.smoking = data.get('smoking', False)
        self.exercise_frequency = data.get('exercise_frequency', 0)
        self.family_history = data.get('family_history', [])
        
    def to_feature_vector(self) -> List[float]:
        """Convert health metrics to feature vector for ML model."""
        # Convert categorical variables to numerical
        gender_encoded = 1.0 if self.gender.lower() == 'male' else 0.0
        smoking_encoded = 1.0 if self.smoking else 0.0
        family_history_count = len(self.family_history) if self.family_history else 0.0
        
        return [
            float(self.age),
            gender_encoded,
            float(self.heart_rate),
            float(self.blood_pressure_systolic),
            float(self.blood_pressure_diastolic),
            float(self.cholesterol),
            float(self.glucose),
            float(self.bmi),
            smoking_encoded,
            float(self.exercise_frequency),
            family_history_count
        ]


class TimeSeriesData:
    """Data class for time series health data used in anomaly detection."""
    
    def __init__(self, data: Dict[str, Any]):
        self.timestamps = data.get('timestamps', [])
        self.values = data.get('values', [])
        self.metric_name = data.get('metric_name', 'unknown')
        self.patient_id = data.get('patient_id', '')
        
    def to_model_input(self) -> Dict[str, Any]:
        """Convert time series data to model input format."""
        return {
            'instances': [{
                'timestamps': self.timestamps,
                'values': self.values,
                'metric_name': self.metric_name
            }]
        }


class RiskAssessment:
    """Data class for risk assessment results."""
    
    def __init__(self, risk_score: float, risk_factors: List[str], 
                 confidence: float, recommendations: List[str]):
        self.risk_score = risk_score
        self.risk_factors = risk_factors
        self.confidence = confidence
        self.recommendations = recommendations
        self.assessment_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert risk assessment to dictionary."""
        return {
            'risk_score': self.risk_score,
            'risk_factors': self.risk_factors,
            'confidence': self.confidence,
            'recommendations': self.recommendations,
            'assessment_time': self.assessment_time.isoformat()
        }


class AnomalyReport:
    """Data class for anomaly detection results."""
    
    def __init__(self, anomalies: List[Dict[str, Any]], 
                 anomaly_score: float, threshold: float):
        self.anomalies = anomalies
        self.anomaly_score = anomaly_score
        self.threshold = threshold
        self.detection_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert anomaly report to dictionary."""
        return {
            'anomalies': self.anomalies,
            'anomaly_score': self.anomaly_score,
            'threshold': self.threshold,
            'detection_time': self.detection_time.isoformat()
        }


class SageMakerClient:
    """AWS SageMaker service client for ML model inference."""
    
    def __init__(self):
        self.region = settings.AWS_REGION
        self.endpoint_name = settings.SAGEMAKER_ENDPOINT_NAME
        
        # Configure boto3 client with retry logic
        config = Config(
            region_name=self.region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        self.runtime_client = boto3.client(
            'sagemaker-runtime',
            config=config,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        self.sagemaker_client = boto3.client(
            'sagemaker',
            config=config,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Circuit breakers for different operations
        self.risk_prediction_cb = CircuitBreaker()
        self.anomaly_detection_cb = CircuitBreaker()
        
        logger.info(f"SageMaker client initialized for region {self.region}")
    
    async def _invoke_endpoint_with_retry(self, endpoint_name: str, payload: Dict[str, Any], 
                                        circuit_breaker: CircuitBreaker, max_retries: int = 3) -> Dict[str, Any]:
        """
        Invoke SageMaker endpoint with retry logic and circuit breaker.
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            payload: Request payload for the model
            circuit_breaker: Circuit breaker instance for this operation
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict containing the model response
            
        Raises:
            SageMakerServiceError: When service is unavailable
            SageMakerModelError: When model inference fails
        """
        if not circuit_breaker.can_execute():
            raise SageMakerServiceError("Circuit breaker is OPEN - service unavailable")
        
        if not endpoint_name:
            raise SageMakerEndpointError("SageMaker endpoint name not configured")
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Convert to async call using asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.runtime_client.invoke_endpoint(
                        EndpointName=endpoint_name,
                        Body=json.dumps(payload),
                        ContentType='application/json',
                        Accept='application/json'
                    )
                )
                
                # Parse response
                response_body = json.loads(response['Body'].read().decode())
                
                # Record success for circuit breaker
                circuit_breaker.record_success()
                
                logger.debug(f"SageMaker endpoint {endpoint_name} invoked successfully on attempt {attempt + 1}")
                return response_body
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ModelError':
                    last_exception = SageMakerModelError(f"Model inference error: {e}")
                    break  # Don't retry for model errors
                elif error_code == 'ValidationException':
                    last_exception = SageMakerModelError(f"Validation error: {e}")
                    break  # Don't retry for validation errors
                elif error_code in ['ThrottlingException', 'ServiceUnavailable']:
                    last_exception = SageMakerServiceError(f"Service unavailable: {e}")
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) * 1
                        logger.warning(f"Service unavailable, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        continue
                else:
                    last_exception = SageMakerServiceError(f"AWS service error: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(1)
                        continue
                        
            except BotoCoreError as e:
                last_exception = SageMakerServiceError(f"Boto3 error: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                    
            except Exception as e:
                last_exception = SageMakerServiceError(f"Unexpected error: {e}")
                break
        
        # Record failure for circuit breaker
        circuit_breaker.record_failure()
        
        logger.error(f"SageMaker endpoint {endpoint_name} invocation failed after {max_retries + 1} attempts")
        raise last_exception
    
    async def predict_risk_factors(self, health_metrics: HealthMetrics) -> RiskAssessment:
        """
        Predict health risk factors using trained ML models.
        
        Args:
            health_metrics: Health metrics data for risk prediction
            
        Returns:
            RiskAssessment: Predicted risk assessment
            
        Raises:
            SageMakerServiceError: When service call fails
        """
        try:
            # Prepare input data for the model
            feature_vector = health_metrics.to_feature_vector()
            
            payload = {
                'instances': [feature_vector]
            }
            
            logger.info("Predicting health risk factors with SageMaker")
            
            # Use a mock endpoint name if not configured for development
            endpoint_name = self.endpoint_name or "health-risk-prediction-endpoint"
            
            try:
                response = await self._invoke_endpoint_with_retry(
                    endpoint_name, payload, self.risk_prediction_cb
                )
                
                # Parse model response
                predictions = response.get('predictions', [])
                if not predictions:
                    raise SageMakerModelError("No predictions returned from model")
                
                prediction = predictions[0]
                
                # Extract risk assessment components
                risk_score = float(prediction.get('risk_score', 0.5))
                confidence = float(prediction.get('confidence', 0.7))
                
                # Generate risk factors based on feature importance
                risk_factors = self._extract_risk_factors(health_metrics, prediction)
                
                # Generate recommendations based on risk factors
                recommendations = self._generate_recommendations(risk_factors, risk_score)
                
                assessment = RiskAssessment(
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    confidence=confidence,
                    recommendations=recommendations
                )
                
                logger.info(f"Risk prediction completed with score: {risk_score:.2f}")
                return assessment
                
            except SageMakerEndpointError:
                # Fallback to mock prediction for development
                logger.warning("SageMaker endpoint not available, using mock prediction")
                return self._mock_risk_prediction(health_metrics)
                
        except Exception as e:
            logger.error(f"Failed to predict risk factors: {e}")
            raise
    
    async def detect_anomalies(self, time_series_data: TimeSeriesData) -> AnomalyReport:
        """
        Detect anomalies in health data patterns using ML models.
        
        Args:
            time_series_data: Time series health data for anomaly detection
            
        Returns:
            AnomalyReport: Detected anomalies and analysis
            
        Raises:
            SageMakerServiceError: When service call fails
        """
        try:
            # Prepare input data for anomaly detection model
            payload = time_series_data.to_model_input()
            
            logger.info(f"Detecting anomalies in {time_series_data.metric_name} data")
            
            # Use a mock endpoint name if not configured for development
            endpoint_name = self.endpoint_name or "health-anomaly-detection-endpoint"
            
            try:
                response = await self._invoke_endpoint_with_retry(
                    endpoint_name, payload, self.anomaly_detection_cb
                )
                
                # Parse anomaly detection response
                anomaly_score = float(response.get('anomaly_score', 0.0))
                threshold = float(response.get('threshold', 0.5))
                anomalies = response.get('anomalies', [])
                
                report = AnomalyReport(
                    anomalies=anomalies,
                    anomaly_score=anomaly_score,
                    threshold=threshold
                )
                
                logger.info(f"Anomaly detection completed with score: {anomaly_score:.2f}")
                return report
                
            except SageMakerEndpointError:
                # Fallback to mock anomaly detection for development
                logger.warning("SageMaker endpoint not available, using mock anomaly detection")
                return self._mock_anomaly_detection(time_series_data)
                
        except Exception as e:
            logger.error(f"Failed to detect anomalies: {e}")
            raise
    
    def _extract_risk_factors(self, health_metrics: HealthMetrics, prediction: Dict[str, Any]) -> List[str]:
        """Extract risk factors based on health metrics and model prediction."""
        risk_factors = []
        
        # Feature importance from model (mock values for development)
        feature_importance = prediction.get('feature_importance', {})
        
        # Check individual risk factors based on thresholds
        if health_metrics.age > 65:
            risk_factors.append("Advanced age")
        
        if health_metrics.blood_pressure_systolic > 140 or health_metrics.blood_pressure_diastolic > 90:
            risk_factors.append("High blood pressure")
        
        if health_metrics.cholesterol > 240:
            risk_factors.append("High cholesterol")
        
        if health_metrics.glucose > 126:
            risk_factors.append("Elevated glucose levels")
        
        if health_metrics.bmi > 30:
            risk_factors.append("Obesity")
        
        if health_metrics.smoking:
            risk_factors.append("Smoking")
        
        if health_metrics.exercise_frequency < 2:
            risk_factors.append("Sedentary lifestyle")
        
        if health_metrics.family_history:
            risk_factors.append("Family history of disease")
        
        return risk_factors
    
    def _generate_recommendations(self, risk_factors: List[str], risk_score: float) -> List[str]:
        """Generate health recommendations based on risk factors."""
        recommendations = []
        
        if "High blood pressure" in risk_factors:
            recommendations.append("Monitor blood pressure regularly and consider dietary changes")
        
        if "High cholesterol" in risk_factors:
            recommendations.append("Adopt a heart-healthy diet low in saturated fats")
        
        if "Elevated glucose levels" in risk_factors:
            recommendations.append("Monitor blood sugar levels and consider diabetes screening")
        
        if "Obesity" in risk_factors:
            recommendations.append("Develop a weight management plan with healthcare provider")
        
        if "Smoking" in risk_factors:
            recommendations.append("Consider smoking cessation programs")
        
        if "Sedentary lifestyle" in risk_factors:
            recommendations.append("Increase physical activity to at least 150 minutes per week")
        
        if risk_score > 0.7:
            recommendations.append("Schedule comprehensive health evaluation with healthcare provider")
        
        if not recommendations:
            recommendations.append("Continue maintaining healthy lifestyle habits")
        
        return recommendations
    
    def _mock_risk_prediction(self, health_metrics: HealthMetrics) -> RiskAssessment:
        """Generate mock risk prediction for development/testing."""
        # Simple risk calculation based on basic factors
        risk_score = 0.3  # Base risk
        
        if health_metrics.age > 65:
            risk_score += 0.2
        if health_metrics.blood_pressure_systolic > 140:
            risk_score += 0.15
        if health_metrics.cholesterol > 240:
            risk_score += 0.1
        if health_metrics.smoking:
            risk_score += 0.15
        if health_metrics.bmi > 30:
            risk_score += 0.1
        
        risk_score = min(risk_score, 1.0)
        
        risk_factors = self._extract_risk_factors(health_metrics, {})
        recommendations = self._generate_recommendations(risk_factors, risk_score)
        
        return RiskAssessment(
            risk_score=risk_score,
            risk_factors=risk_factors,
            confidence=0.75,
            recommendations=recommendations
        )
    
    def _mock_anomaly_detection(self, time_series_data: TimeSeriesData) -> AnomalyReport:
        """Generate mock anomaly detection for development/testing."""
        # Simple anomaly detection based on statistical analysis
        if not time_series_data.values:
            return AnomalyReport(anomalies=[], anomaly_score=0.0, threshold=0.5)
        
        values = np.array(time_series_data.values)
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        # Detect values outside 2 standard deviations
        anomalies = []
        anomaly_score = 0.0
        
        for i, (timestamp, value) in enumerate(zip(time_series_data.timestamps, values)):
            z_score = abs((value - mean_val) / std_val) if std_val > 0 else 0
            
            if z_score > 2:
                anomalies.append({
                    'timestamp': timestamp,
                    'value': value,
                    'z_score': z_score,
                    'severity': 'high' if z_score > 3 else 'moderate'
                })
                anomaly_score = max(anomaly_score, min(z_score / 4, 1.0))
        
        return AnomalyReport(
            anomalies=anomalies,
            anomaly_score=anomaly_score,
            threshold=0.5
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on SageMaker service.
        
        Returns:
            Dict containing health check results
        """
        try:
            # Check if we can list endpoints (basic connectivity test)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.sagemaker_client.list_endpoints(MaxResults=1)
            )
            
            return {
                "status": "healthy",
                "service": "sagemaker",
                "endpoint_name": self.endpoint_name,
                "region": self.region,
                "risk_prediction_cb_state": self.risk_prediction_cb.state,
                "anomaly_detection_cb_state": self.anomaly_detection_cb.state,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "sagemaker",
                "error": str(e),
                "risk_prediction_cb_state": self.risk_prediction_cb.state,
                "anomaly_detection_cb_state": self.anomaly_detection_cb.state,
                "timestamp": datetime.now().isoformat()
            }


# Global SageMaker client instance
_sagemaker_client: Optional[SageMakerClient] = None


def get_sagemaker_client() -> SageMakerClient:
    """Get or create the global SageMaker client instance."""
    global _sagemaker_client
    if _sagemaker_client is None:
        _sagemaker_client = SageMakerClient()
    return _sagemaker_client


async def init_sagemaker() -> bool:
    """Initialize SageMaker client and verify connectivity."""
    try:
        client = get_sagemaker_client()
        health_result = await client.health_check()
        
        if health_result["status"] == "healthy":
            logger.info("SageMaker client initialized successfully")
            return True
        else:
            logger.error(f"SageMaker health check failed: {health_result}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to initialize SageMaker client: {e}")
        return False


async def close_sagemaker() -> None:
    """Close SageMaker client connections."""
    global _sagemaker_client
    if _sagemaker_client:
        logger.info("SageMaker client connections closed")
        _sagemaker_client = None