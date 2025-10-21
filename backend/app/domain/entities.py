"""
Core domain entities for the Health Insight Agent.

This module contains the fundamental business entities that represent
the core concepts in the health analysis domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class VitalType(Enum):
    """Types of vital signs that can be measured."""
    HEART_RATE = "heart_rate"
    BLOOD_PRESSURE_SYSTOLIC = "blood_pressure_systolic"
    BLOOD_PRESSURE_DIASTOLIC = "blood_pressure_diastolic"
    TEMPERATURE = "temperature"
    RESPIRATORY_RATE = "respiratory_rate"
    OXYGEN_SATURATION = "oxygen_saturation"


class LabResultType(Enum):
    """Types of laboratory test results."""
    BLOOD_GLUCOSE = "blood_glucose"
    CHOLESTEROL_TOTAL = "cholesterol_total"
    CHOLESTEROL_HDL = "cholesterol_hdl"
    CHOLESTEROL_LDL = "cholesterol_ldl"
    HEMOGLOBIN_A1C = "hemoglobin_a1c"
    WHITE_BLOOD_CELL_COUNT = "white_blood_cell_count"
    RED_BLOOD_CELL_COUNT = "red_blood_cell_count"
    PLATELET_COUNT = "platelet_count"


class SeverityLevel(Enum):
    """Severity levels for symptoms and assessments."""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class RiskLevel(Enum):
    """Risk levels for health assessments."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class VitalSigns:
    """Represents a collection of vital sign measurements."""
    
    heart_rate: Optional[int] = None  # beats per minute
    blood_pressure_systolic: Optional[int] = None  # mmHg
    blood_pressure_diastolic: Optional[int] = None  # mmHg
    temperature: Optional[float] = None  # Celsius
    respiratory_rate: Optional[int] = None  # breaths per minute
    oxygen_saturation: Optional[float] = None  # percentage
    measured_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate vital signs values."""
        if self.heart_rate is not None and not (40 <= self.heart_rate <= 200):
            raise ValueError("Heart rate must be between 40 and 200 bpm")
        
        if self.blood_pressure_systolic is not None and not (70 <= self.blood_pressure_systolic <= 250):
            raise ValueError("Systolic blood pressure must be between 70 and 250 mmHg")
        
        if self.blood_pressure_diastolic is not None and not (40 <= self.blood_pressure_diastolic <= 150):
            raise ValueError("Diastolic blood pressure must be between 40 and 150 mmHg")
        
        if self.temperature is not None and not (35.0 <= self.temperature <= 42.0):
            raise ValueError("Temperature must be between 35.0 and 42.0 Celsius")
        
        if self.respiratory_rate is not None and not (8 <= self.respiratory_rate <= 40):
            raise ValueError("Respiratory rate must be between 8 and 40 breaths per minute")
        
        if self.oxygen_saturation is not None and not (70.0 <= self.oxygen_saturation <= 100.0):
            raise ValueError("Oxygen saturation must be between 70.0 and 100.0 percent")


@dataclass
class LabResult:
    """Represents a laboratory test result."""
    
    test_type: LabResultType
    value: float
    unit: str
    reference_range_min: Optional[float] = None
    reference_range_max: Optional[float] = None
    tested_at: datetime = field(default_factory=datetime.utcnow)
    lab_name: Optional[str] = None
    
    def is_within_normal_range(self) -> Optional[bool]:
        """Check if the result is within the normal reference range."""
        if self.reference_range_min is None or self.reference_range_max is None:
            return None
        return self.reference_range_min <= self.value <= self.reference_range_max
    
    def __post_init__(self):
        """Validate lab result values."""
        if self.value < 0:
            raise ValueError("Lab result value cannot be negative")
        
        if (self.reference_range_min is not None and 
            self.reference_range_max is not None and 
            self.reference_range_min >= self.reference_range_max):
            raise ValueError("Reference range minimum must be less than maximum")


@dataclass
class Symptom:
    """Represents a patient-reported symptom."""
    
    name: str
    severity: SeverityLevel
    duration_days: Optional[int] = None
    description: Optional[str] = None
    reported_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate symptom data."""
        if not self.name or not self.name.strip():
            raise ValueError("Symptom name cannot be empty")
        
        if self.duration_days is not None and self.duration_days < 0:
            raise ValueError("Symptom duration cannot be negative")


@dataclass
class MedicalHistory:
    """Represents a patient's medical history."""
    
    conditions: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    surgeries: List[str] = field(default_factory=list)
    family_history: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def add_condition(self, condition: str) -> None:
        """Add a medical condition to the history."""
        if condition and condition.strip() and condition not in self.conditions:
            self.conditions.append(condition.strip())
            self.last_updated = datetime.utcnow()
    
    def add_medication(self, medication: str) -> None:
        """Add a medication to the history."""
        if medication and medication.strip() and medication not in self.medications:
            self.medications.append(medication.strip())
            self.last_updated = datetime.utcnow()


@dataclass
class HealthData:
    """Represents comprehensive health data for a patient."""
    
    patient_id: str
    vitals: Optional[VitalSigns] = None
    lab_results: List[LabResult] = field(default_factory=list)
    symptoms: List[Symptom] = field(default_factory=list)
    medical_history: Optional[MedicalHistory] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_id: UUID = field(default_factory=uuid4)
    
    def __post_init__(self):
        """Validate health data."""
        if not self.patient_id or not self.patient_id.strip():
            raise ValueError("Patient ID cannot be empty")
    
    def has_complete_vitals(self) -> bool:
        """Check if all essential vital signs are present."""
        if not self.vitals:
            return False
        
        essential_vitals = [
            self.vitals.heart_rate,
            self.vitals.blood_pressure_systolic,
            self.vitals.blood_pressure_diastolic
        ]
        return all(vital is not None for vital in essential_vitals)
    
    def get_abnormal_lab_results(self) -> List[LabResult]:
        """Get lab results that are outside normal ranges."""
        abnormal_results = []
        for result in self.lab_results:
            if result.is_within_normal_range() is False:
                abnormal_results.append(result)
        return abnormal_results