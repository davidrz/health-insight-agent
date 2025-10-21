"""
Security utilities for Health Insight Agent.

This module provides encryption, tokenization, and data protection utilities
for handling sensitive health information.
"""

import hashlib
import hmac
import secrets
import base64
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import settings

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manages AES-256 encryption for sensitive health data."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            encryption_key: Base64 encoded encryption key. If None, uses settings.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Generate key from secret key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'health_insight_salt',  # In production, use random salt per installation
                iterations=100000,
            )
            self.key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
        
        self.cipher_suite = Fernet(self.key)
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt sensitive data using AES-256.
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            Base64 encoded encrypted data
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted_data = self.cipher_suite.encrypt(data)
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise SecurityError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted data as string
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise SecurityError(f"Failed to decrypt data: {e}")
    
    def encrypt_dict(self, data: Dict[str, Any], fields_to_encrypt: list) -> Dict[str, Any]:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields_to_encrypt: List of field names to encrypt
            
        Returns:
            Dictionary with encrypted fields
        """
        encrypted_data = data.copy()
        
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encrypt(str(encrypted_data[field]))
                encrypted_data[f"{field}_encrypted"] = True
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields_to_decrypt: list) -> Dict[str, Any]:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt
            
        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()
        
        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data.get(f"{field}_encrypted"):
                decrypted_data[field] = self.decrypt(decrypted_data[field])
                decrypted_data.pop(f"{field}_encrypted", None)
        
        return decrypted_data


class PIITokenizer:
    """Tokenizes personally identifiable information (PII) for patient data."""
    
    def __init__(self):
        """Initialize PII tokenizer with HMAC-based tokenization."""
        self.secret_key = settings.SECRET_KEY.encode()
    
    def tokenize_patient_id(self, patient_id: str) -> str:
        """
        Create a secure token for patient ID.
        
        Args:
            patient_id: Original patient identifier
            
        Returns:
            Tokenized patient ID
        """
        try:
            # Create HMAC-based token
            token_data = f"{patient_id}:{datetime.utcnow().isoformat()}"
            token_hash = hmac.new(
                self.secret_key,
                token_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Combine with timestamp for uniqueness
            timestamp = int(datetime.utcnow().timestamp())
            token = f"pt_{timestamp}_{token_hash[:16]}"
            
            return token
            
        except Exception as e:
            logger.error(f"Patient ID tokenization failed: {e}")
            raise SecurityError(f"Failed to tokenize patient ID: {e}")
    
    def tokenize_pii_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tokenize PII fields in health data.
        
        Args:
            data: Dictionary containing health data
            
        Returns:
            Dictionary with tokenized PII fields
        """
        pii_fields = [
            'patient_name', 'email', 'phone', 'address', 
            'social_security', 'medical_record_number'
        ]
        
        tokenized_data = data.copy()
        
        for field in pii_fields:
            if field in tokenized_data and tokenized_data[field]:
                original_value = tokenized_data[field]
                token = self._generate_field_token(field, original_value)
                tokenized_data[field] = token
                tokenized_data[f"{field}_tokenized"] = True
        
        return tokenized_data
    
    def _generate_field_token(self, field_name: str, value: str) -> str:
        """Generate a token for a specific PII field."""
        token_data = f"{field_name}:{value}:{secrets.token_hex(8)}"
        token_hash = hmac.new(
            self.secret_key,
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"tok_{field_name}_{token_hash[:12]}"


class DataSanitizer:
    """Sanitizes input and output data for AI model interactions."""
    
    @staticmethod
    def sanitize_input(data: str) -> str:
        """
        Sanitize input data before sending to AI models.
        
        Args:
            data: Input data to sanitize
            
        Returns:
            Sanitized data
        """
        if not data:
            return ""
        
        # Remove potential injection patterns
        sanitized = data.strip()
        
        # Remove or escape potentially dangerous characters
        dangerous_patterns = [
            '<script', '</script>', 'javascript:', 'data:',
            'eval(', 'exec(', 'import ', 'from ', '__'
        ]
        
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, f"[FILTERED:{pattern}]")
        
        # Limit length to prevent DoS
        max_length = 10000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "[TRUNCATED]"
        
        return sanitized
    
    @staticmethod
    def sanitize_ai_output(output: str) -> str:
        """
        Sanitize AI model output before returning to users.
        
        Args:
            output: AI model output to sanitize
            
        Returns:
            Sanitized output
        """
        if not output:
            return ""
        
        sanitized = output.strip()
        
        # Remove potential sensitive information patterns
        sensitive_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card pattern
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email pattern
        ]
        
        import re
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized)
        
        return sanitized
    
    @staticmethod
    def filter_health_data_output(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive fields from health data output.
        
        Args:
            data: Health data dictionary
            
        Returns:
            Filtered data dictionary
        """
        # Fields that should never be exposed in API responses
        sensitive_fields = [
            'raw_patient_id', 'ssn', 'medical_record_number',
            'insurance_id', 'emergency_contact', 'next_of_kin'
        ]
        
        filtered_data = data.copy()
        
        for field in sensitive_fields:
            filtered_data.pop(field, None)
        
        return filtered_data


class AuditLogger:
    """Logs all data access and modifications for compliance."""
    
    def __init__(self):
        """Initialize audit logger."""
        self.logger = logging.getLogger('audit')
        
        # Configure audit logger with separate handler
        if not self.logger.handlers:
            handler = logging.FileHandler('audit.log')
            formatter = logging.Formatter(
                '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_data_access(
        self, 
        user_id: str, 
        patient_id: str, 
        action: str, 
        resource: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Log data access events.
        
        Args:
            user_id: ID of user performing action
            patient_id: ID of patient whose data is accessed
            action: Action performed (READ, CREATE, UPDATE, DELETE)
            resource: Resource accessed (health_data, insights, etc.)
            ip_address: Client IP address
            user_agent: Client user agent
            additional_data: Additional context data
        """
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'patient_id': patient_id,
            'action': action,
            'resource': resource,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': secrets.token_hex(16),
        }
        
        if additional_data:
            audit_entry['additional_data'] = additional_data
        
        self.logger.info(f"DATA_ACCESS: {audit_entry}")
    
    def log_security_event(
        self, 
        event_type: str, 
        user_id: Optional[str], 
        description: str,
        severity: str = "INFO",
        ip_address: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Log security-related events.
        
        Args:
            event_type: Type of security event
            user_id: User ID if applicable
            description: Event description
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
            ip_address: Client IP address
            additional_data: Additional context data
        """
        security_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'description': description,
            'severity': severity,
            'ip_address': ip_address,
        }
        
        if additional_data:
            security_entry['additional_data'] = additional_data
        
        self.logger.warning(f"SECURITY_EVENT: {security_entry}")


from app.core.exceptions import SecurityError as CoreSecurityError

class SecurityError(CoreSecurityError):
    """Custom exception for security-related errors."""
    pass


# Global instances
encryption_manager = EncryptionManager()
pii_tokenizer = PIITokenizer()
data_sanitizer = DataSanitizer()
audit_logger = AuditLogger()