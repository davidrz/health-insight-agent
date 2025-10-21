"""
Repository interfaces for the Health Insight Agent domain.

This module defines the abstract interfaces for data persistence
following the Repository pattern and Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from .entities import HealthData
from .value_objects import InsightReport


class HealthDataRepository(ABC):
    """Abstract repository interface for health data persistence."""
    
    @abstractmethod
    async def save(self, health_data: HealthData) -> HealthData:
        """
        Save health data to the repository.
        
        Args:
            health_data: The health data to save
            
        Returns:
            The saved health data with any generated IDs
            
        Raises:
            RepositoryError: If the save operation fails
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, data_id: UUID) -> Optional[HealthData]:
        """
        Retrieve health data by its unique identifier.
        
        Args:
            data_id: The unique identifier of the health data
            
        Returns:
            The health data if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_by_patient_id(self, patient_id: str) -> List[HealthData]:
        """
        Retrieve all health data for a specific patient.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            List of health data entries for the patient
        """
        pass
    
    @abstractmethod
    async def get_by_patient_id_and_date_range(
        self, 
        patient_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[HealthData]:
        """
        Retrieve health data for a patient within a date range.
        
        Args:
            patient_id: The patient's unique identifier
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            List of health data entries within the date range
        """
        pass
    
    @abstractmethod
    async def update(self, health_data: HealthData) -> HealthData:
        """
        Update existing health data in the repository.
        
        Args:
            health_data: The health data to update
            
        Returns:
            The updated health data
            
        Raises:
            RepositoryError: If the update operation fails
            NotFoundError: If the health data doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete(self, data_id: UUID) -> bool:
        """
        Delete health data from the repository.
        
        Args:
            data_id: The unique identifier of the health data to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def exists(self, data_id: UUID) -> bool:
        """
        Check if health data exists in the repository.
        
        Args:
            data_id: The unique identifier to check
            
        Returns:
            True if the health data exists, False otherwise
        """
        pass


class InsightReportRepository(ABC):
    """Abstract repository interface for insight report persistence."""
    
    @abstractmethod
    async def save(self, report: InsightReport) -> InsightReport:
        """
        Save an insight report to the repository.
        
        Args:
            report: The insight report to save
            
        Returns:
            The saved insight report with any generated IDs
            
        Raises:
            RepositoryError: If the save operation fails
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, report_id: UUID) -> Optional[InsightReport]:
        """
        Retrieve an insight report by its unique identifier.
        
        Args:
            report_id: The unique identifier of the insight report
            
        Returns:
            The insight report if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_by_patient_id(self, patient_id: str) -> List[InsightReport]:
        """
        Retrieve all insight reports for a specific patient.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            List of insight reports for the patient, ordered by generation date
        """
        pass
    
    @abstractmethod
    async def get_latest_by_patient_id(self, patient_id: str) -> Optional[InsightReport]:
        """
        Retrieve the most recent insight report for a patient.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            The most recent insight report if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_by_patient_id_and_date_range(
        self, 
        patient_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[InsightReport]:
        """
        Retrieve insight reports for a patient within a date range.
        
        Args:
            patient_id: The patient's unique identifier
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            List of insight reports within the date range
        """
        pass
    
    @abstractmethod
    async def update(self, report: InsightReport) -> InsightReport:
        """
        Update an existing insight report in the repository.
        
        Args:
            report: The insight report to update
            
        Returns:
            The updated insight report
            
        Raises:
            RepositoryError: If the update operation fails
            NotFoundError: If the insight report doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete(self, report_id: UUID) -> bool:
        """
        Delete an insight report from the repository.
        
        Args:
            report_id: The unique identifier of the report to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_reports_by_confidence_threshold(
        self, 
        min_confidence: float
    ) -> List[InsightReport]:
        """
        Retrieve insight reports with confidence above a threshold.
        
        Args:
            min_confidence: Minimum confidence score (0.0 to 1.0)
            
        Returns:
            List of insight reports meeting the confidence threshold
        """
        pass


class PatientRepository(ABC):
    """Abstract repository interface for patient data management."""
    
    @abstractmethod
    async def create_patient(self, patient_id: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Create a new patient record.
        
        Args:
            patient_id: The unique identifier for the patient
            metadata: Optional metadata associated with the patient
            
        Returns:
            True if creation was successful, False otherwise
            
        Raises:
            RepositoryError: If the creation operation fails
            DuplicateError: If the patient already exists
        """
        pass
    
    @abstractmethod
    async def patient_exists(self, patient_id: str) -> bool:
        """
        Check if a patient exists in the repository.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            True if the patient exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_patient_metadata(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for a specific patient.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            Patient metadata if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update_patient_metadata(
        self, 
        patient_id: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Update metadata for a specific patient.
        
        Args:
            patient_id: The patient's unique identifier
            metadata: Updated metadata
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete_patient(self, patient_id: str) -> bool:
        """
        Delete a patient and all associated data.
        
        Args:
            patient_id: The patient's unique identifier
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_patients(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None
    ) -> List[str]:
        """
        List all patient IDs in the repository.
        
        Args:
            limit: Maximum number of patients to return
            offset: Number of patients to skip
            
        Returns:
            List of patient IDs
        """
        pass


# Custom exceptions for repository operations
class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class NotFoundError(RepositoryError):
    """Raised when a requested entity is not found."""
    pass


class DuplicateError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""
    pass


class ValidationError(RepositoryError):
    """Raised when entity validation fails during repository operations."""
    pass