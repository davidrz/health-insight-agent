"""
Encryption service for health data repositories.

This module provides encryption/decryption services for sensitive health data
stored in the database.
"""

import logging
from typing import Dict, Any, List, Optional
from app.core.security import encryption_manager, pii_tokenizer, data_sanitizer
from app.domain.entities import HealthData, VitalSigns, LabResult, Symptom, MedicalHistory

logger = logging.getLogger(__name__)


class HealthDataEncryptionService:
    """Service for encrypting and decrypting health data."""
    
    def __init__(self):
        """Initialize encryption service."""
        self.encryption_manager = encryption_manager
        self.pii_tokenizer = pii_tokenizer
        self.data_sanitizer = data_sanitizer
        
        # Define which fields should be encrypted
        self.encrypted_fields = {
            'vitals': ['heart_rate', 'blood_pressure_systolic', 'blood_pressure_diastolic', 
                      'temperature', 'respiratory_rate', 'oxygen_saturation'],
            'lab_results': ['value', 'lab_name'],
            'symptoms': ['name', 'description'],
            'medical_history': ['conditions', 'medications', 'allergies', 'surgeries', 'family_history']
        }
        
        # Define PII fields that should be tokenized
        self.pii_fields = ['patient_id', 'lab_name']
    
    def encrypt_health_data(self, health_data: HealthData) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in health data before storage.
        
        Args:
            health_data: HealthData entity to encrypt
            
        Returns:
            Dictionary with encrypted data
        """
        try:
            # Start with basic serialization
            data = self._serialize_health_data(health_data)
            
            # Tokenize patient ID
            if 'patient_id' in data:
                data['patient_id_token'] = self.pii_tokenizer.tokenize_patient_id(data['patient_id'])
            
            # Encrypt vitals
            if 'vitals' in data and data['vitals']:
                data['vitals'] = self.encryption_manager.encrypt_dict(
                    data['vitals'], 
                    self.encrypted_fields['vitals']
                )
            
            # Encrypt lab results
            if 'lab_results' in data and data['lab_results']:
                encrypted_results = []
                for result in data['lab_results']:
                    encrypted_result = self.encryption_manager.encrypt_dict(
                        result, 
                        self.encrypted_fields['lab_results']
                    )
                    encrypted_results.append(encrypted_result)
                data['lab_results'] = encrypted_results
            
            # Encrypt symptoms
            if 'symptoms' in data and data['symptoms']:
                encrypted_symptoms = []
                for symptom in data['symptoms']:
                    encrypted_symptom = self.encryption_manager.encrypt_dict(
                        symptom, 
                        self.encrypted_fields['symptoms']
                    )
                    encrypted_symptoms.append(encrypted_symptom)
                data['symptoms'] = encrypted_symptoms
            
            # Encrypt medical history
            if 'medical_history' in data and data['medical_history']:
                data['medical_history'] = self.encryption_manager.encrypt_dict(
                    data['medical_history'], 
                    self.encrypted_fields['medical_history']
                )
            
            # Mark as encrypted
            data['_encrypted'] = True
            data['_encryption_version'] = '1.0'
            
            logger.debug(f"Encrypted health data for patient {health_data.patient_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to encrypt health data: {e}")
            raise
    
    def decrypt_health_data(self, encrypted_data: Dict[str, Any], patient_id: str) -> HealthData:
        """
        Decrypt health data after retrieval from storage.
        
        Args:
            encrypted_data: Dictionary with encrypted data
            patient_id: Patient ID for the data
            
        Returns:
            Decrypted HealthData entity
        """
        try:
            # Check if data is encrypted
            if not encrypted_data.get('_encrypted', False):
                # Data is not encrypted, deserialize normally
                return self._deserialize_health_data(encrypted_data, patient_id)
            
            # Create a copy for decryption
            data = encrypted_data.copy()
            
            # Decrypt vitals
            if 'vitals' in data and data['vitals']:
                data['vitals'] = self.encryption_manager.decrypt_dict(
                    data['vitals'], 
                    self.encrypted_fields['vitals']
                )
            
            # Decrypt lab results
            if 'lab_results' in data and data['lab_results']:
                decrypted_results = []
                for result in data['lab_results']:
                    decrypted_result = self.encryption_manager.decrypt_dict(
                        result, 
                        self.encrypted_fields['lab_results']
                    )
                    decrypted_results.append(decrypted_result)
                data['lab_results'] = decrypted_results
            
            # Decrypt symptoms
            if 'symptoms' in data and data['symptoms']:
                decrypted_symptoms = []
                for symptom in data['symptoms']:
                    decrypted_symptom = self.encryption_manager.decrypt_dict(
                        symptom, 
                        self.encrypted_fields['symptoms']
                    )
                    decrypted_symptoms.append(decrypted_symptom)
                data['symptoms'] = decrypted_symptoms
            
            # Decrypt medical history
            if 'medical_history' in data and data['medical_history']:
                data['medical_history'] = self.encryption_manager.decrypt_dict(
                    data['medical_history'], 
                    self.encrypted_fields['medical_history']
                )
            
            # Remove encryption metadata
            data.pop('_encrypted', None)
            data.pop('_encryption_version', None)
            data.pop('patient_id_token', None)
            
            logger.debug(f"Decrypted health data for patient {patient_id}")
            return self._deserialize_health_data(data, patient_id)
            
        except Exception as e:
            logger.error(f"Failed to decrypt health data: {e}")
            raise
    
    def sanitize_for_ai_processing(self, health_data: HealthData) -> Dict[str, Any]:
        """
        Sanitize health data for AI model processing.
        
        Args:
            health_data: HealthData to sanitize
            
        Returns:
            Sanitized data dictionary safe for AI processing
        """
        try:
            # Serialize to dictionary
            data = self._serialize_health_data(health_data)
            
            # Remove or tokenize PII
            if 'patient_id' in data:
                data['patient_id'] = self.pii_tokenizer.tokenize_patient_id(data['patient_id'])
            
            # Sanitize text fields
            if 'symptoms' in data:
                for symptom in data['symptoms']:
                    if 'name' in symptom:
                        symptom['name'] = self.data_sanitizer.sanitize_input(symptom['name'])
                    if 'description' in symptom:
                        symptom['description'] = self.data_sanitizer.sanitize_input(symptom['description'])
            
            if 'medical_history' in data and data['medical_history']:
                history = data['medical_history']
                for field in ['conditions', 'medications', 'allergies', 'surgeries', 'family_history']:
                    if field in history and isinstance(history[field], list):
                        history[field] = [
                            self.data_sanitizer.sanitize_input(item) 
                            for item in history[field]
                        ]
            
            # Remove sensitive metadata
            data.pop('data_id', None)
            data.pop('timestamp', None)
            
            logger.debug(f"Sanitized health data for AI processing")
            return data
            
        except Exception as e:
            logger.error(f"Failed to sanitize health data for AI: {e}")
            raise
    
    def filter_output_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive information from output data.
        
        Args:
            data: Data to filter
            
        Returns:
            Filtered data safe for API responses
        """
        return self.data_sanitizer.filter_health_data_output(data)
    
    def _serialize_health_data(self, health_data: HealthData) -> Dict[str, Any]:
        """Serialize HealthData to dictionary."""
        data = {
            "data_id": str(health_data.data_id),
            "patient_id": health_data.patient_id,
            "timestamp": health_data.timestamp.isoformat(),
        }
        
        if health_data.vitals:
            data["vitals"] = {
                "heart_rate": health_data.vitals.heart_rate,
                "blood_pressure_systolic": health_data.vitals.blood_pressure_systolic,
                "blood_pressure_diastolic": health_data.vitals.blood_pressure_diastolic,
                "temperature": health_data.vitals.temperature,
                "respiratory_rate": health_data.vitals.respiratory_rate,
                "oxygen_saturation": health_data.vitals.oxygen_saturation,
                "measured_at": health_data.vitals.measured_at.isoformat(),
            }
        
        if health_data.lab_results:
            data["lab_results"] = [
                {
                    "test_type": result.test_type.value,
                    "value": result.value,
                    "unit": result.unit,
                    "reference_range_min": result.reference_range_min,
                    "reference_range_max": result.reference_range_max,
                    "tested_at": result.tested_at.isoformat(),
                    "lab_name": result.lab_name,
                }
                for result in health_data.lab_results
            ]
        
        if health_data.symptoms:
            data["symptoms"] = [
                {
                    "name": symptom.name,
                    "severity": symptom.severity.value,
                    "duration_days": symptom.duration_days,
                    "description": symptom.description,
                    "reported_at": symptom.reported_at.isoformat(),
                }
                for symptom in health_data.symptoms
            ]
        
        if health_data.medical_history:
            data["medical_history"] = {
                "conditions": health_data.medical_history.conditions,
                "medications": health_data.medical_history.medications,
                "allergies": health_data.medical_history.allergies,
                "surgeries": health_data.medical_history.surgeries,
                "family_history": health_data.medical_history.family_history,
                "last_updated": health_data.medical_history.last_updated.isoformat(),
            }
        
        return data
    
    def _deserialize_health_data(self, data: Dict[str, Any], patient_id: str) -> HealthData:
        """Deserialize dictionary to HealthData."""
        from datetime import datetime
        from uuid import UUID
        from app.domain.entities import LabResultType, SeverityLevel
        
        # Parse vitals
        vitals = None
        if "vitals" in data and data["vitals"]:
            vitals_data = data["vitals"]
            vitals = VitalSigns(
                heart_rate=vitals_data.get("heart_rate"),
                blood_pressure_systolic=vitals_data.get("blood_pressure_systolic"),
                blood_pressure_diastolic=vitals_data.get("blood_pressure_diastolic"),
                temperature=vitals_data.get("temperature"),
                respiratory_rate=vitals_data.get("respiratory_rate"),
                oxygen_saturation=vitals_data.get("oxygen_saturation"),
                measured_at=datetime.fromisoformat(vitals_data["measured_at"]),
            )
        
        # Parse lab results
        lab_results = []
        if "lab_results" in data and data["lab_results"]:
            for result_data in data["lab_results"]:
                lab_result = LabResult(
                    test_type=LabResultType(result_data["test_type"]),
                    value=result_data["value"],
                    unit=result_data["unit"],
                    reference_range_min=result_data.get("reference_range_min"),
                    reference_range_max=result_data.get("reference_range_max"),
                    tested_at=datetime.fromisoformat(result_data["tested_at"]),
                    lab_name=result_data.get("lab_name"),
                )
                lab_results.append(lab_result)
        
        # Parse symptoms
        symptoms = []
        if "symptoms" in data and data["symptoms"]:
            for symptom_data in data["symptoms"]:
                symptom = Symptom(
                    name=symptom_data["name"],
                    severity=SeverityLevel(symptom_data["severity"]),
                    duration_days=symptom_data.get("duration_days"),
                    description=symptom_data.get("description"),
                    reported_at=datetime.fromisoformat(symptom_data["reported_at"]),
                )
                symptoms.append(symptom)
        
        # Parse medical history
        medical_history = None
        if "medical_history" in data and data["medical_history"]:
            history_data = data["medical_history"]
            medical_history = MedicalHistory(
                conditions=history_data.get("conditions", []),
                medications=history_data.get("medications", []),
                allergies=history_data.get("allergies", []),
                surgeries=history_data.get("surgeries", []),
                family_history=history_data.get("family_history", []),
                last_updated=datetime.fromisoformat(history_data["last_updated"]),
            )
        
        return HealthData(
            patient_id=patient_id,
            vitals=vitals,
            lab_results=lab_results,
            symptoms=symptoms,
            medical_history=medical_history,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data_id=UUID(data["data_id"]),
        )


# Global instance
health_data_encryption_service = HealthDataEncryptionService()