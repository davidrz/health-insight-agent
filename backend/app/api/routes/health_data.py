"""
Health data endpoints for the Health Insight Agent API.
"""

from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    HealthDataRequest, HealthDataResponse, ErrorResponse,
    PaginationParams, InsightReportsListResponse
)
from app.api.auth import get_current_active_user, User, require_roles
from app.infra.database import get_db_session
from app.domain.entities import HealthData, VitalSigns, LabResult, Symptom, MedicalHistory
from app.domain.value_objects import InsightReport
from app.infra.repositories import HealthDataRepository, InsightReportRepository


router = APIRouter()


@router.post(
    "/health-data",
    response_model=HealthDataResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid health data"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    },
    summary="Upload health data",
    description="Upload patient health data including vitals, lab results, symptoms, and medical history"
)
async def upload_health_data(
    health_data_request: HealthDataRequest,
    current_user: User = Depends(require_roles(["healthcare_provider", "patient"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Upload comprehensive health data for a patient.
    
    - **patient_id**: Unique identifier for the patient
    - **vitals**: Vital signs measurements (optional)
    - **lab_results**: Laboratory test results (optional)
    - **symptoms**: Patient-reported symptoms (optional)
    - **medical_history**: Medical history information (optional)
    
    Requires authentication and appropriate permissions.
    """
    try:
        # Convert request to domain entity
        health_data = _convert_request_to_health_data(health_data_request)
        
        # Validate patient access permissions
        if "patient" in current_user.roles and health_data.patient_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients can only upload their own health data"
            )
        
        # Save health data using repository
        health_repo = HealthDataRepository(db)
        saved_data = await health_repo.save(health_data)
        
        return HealthDataResponse(
            data_id=saved_data.data_id,
            patient_id=saved_data.patient_id,
            timestamp=saved_data.timestamp,
            message="Health data uploaded successfully"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid health data: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload health data"
        )


@router.get(
    "/health-data/{patient_id}",
    response_model=List[HealthDataResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Patient not found"}
    },
    summary="Get patient health data",
    description="Retrieve health data records for a specific patient"
)
async def get_patient_health_data(
    patient_id: str,
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve health data records for a patient.
    
    - **patient_id**: Unique identifier for the patient
    - **limit**: Maximum number of records to return (1-100)
    - **offset**: Number of records to skip for pagination
    
    Returns list of health data records ordered by timestamp (newest first).
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own health data"
        )
    
    try:
        health_repo = HealthDataRepository(db)
        health_records = await health_repo.get_by_patient_id(
            patient_id, limit=limit, offset=offset
        )
        
        if not health_records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No health data found for this patient"
            )
        
        return [
            HealthDataResponse(
                data_id=record.data_id,
                patient_id=record.patient_id,
                timestamp=record.timestamp,
                message="Health data retrieved successfully"
            )
            for record in health_records
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health data"
        )


@router.get(
    "/health-data/{patient_id}/latest",
    response_model=HealthDataResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "No health data found"}
    },
    summary="Get latest health data",
    description="Retrieve the most recent health data record for a patient"
)
async def get_latest_health_data(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve the most recent health data record for a patient.
    
    - **patient_id**: Unique identifier for the patient
    
    Returns the latest health data record.
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own health data"
        )
    
    try:
        health_repo = HealthDataRepository(db)
        latest_record = await health_repo.get_latest_by_patient_id(patient_id)
        
        if not latest_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No health data found for this patient"
            )
        
        return HealthDataResponse(
            data_id=latest_record.data_id,
            patient_id=latest_record.patient_id,
            timestamp=latest_record.timestamp,
            message="Latest health data retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest health data"
        )


def _convert_request_to_health_data(request: HealthDataRequest) -> HealthData:
    """Convert API request to domain entity"""
    # Convert vitals
    vitals = None
    if request.vitals:
        vitals = VitalSigns(
            heart_rate=request.vitals.heart_rate,
            blood_pressure_systolic=request.vitals.blood_pressure_systolic,
            blood_pressure_diastolic=request.vitals.blood_pressure_diastolic,
            temperature=request.vitals.temperature,
            respiratory_rate=request.vitals.respiratory_rate,
            oxygen_saturation=request.vitals.oxygen_saturation,
            measured_at=request.vitals.measured_at or None
        )
    
    # Convert lab results
    lab_results = []
    for lab_req in request.lab_results:
        lab_result = LabResult(
            test_type=lab_req.test_type,
            value=lab_req.value,
            unit=lab_req.unit,
            reference_range_min=lab_req.reference_range_min,
            reference_range_max=lab_req.reference_range_max,
            tested_at=lab_req.tested_at or None,
            lab_name=lab_req.lab_name
        )
        lab_results.append(lab_result)
    
    # Convert symptoms
    symptoms = []
    for symptom_req in request.symptoms:
        symptom = Symptom(
            name=symptom_req.name,
            severity=symptom_req.severity,
            duration_days=symptom_req.duration_days,
            description=symptom_req.description,
            reported_at=symptom_req.reported_at or None
        )
        symptoms.append(symptom)
    
    # Convert medical history
    medical_history = None
    if request.medical_history:
        medical_history = MedicalHistory(
            conditions=request.medical_history.conditions,
            medications=request.medical_history.medications,
            allergies=request.medical_history.allergies,
            surgeries=request.medical_history.surgeries,
            family_history=request.medical_history.family_history,
            last_updated=request.medical_history.last_updated or None
        )
    
    return HealthData(
        patient_id=request.patient_id,
        vitals=vitals,
        lab_results=lab_results,
        symptoms=symptoms,
        medical_history=medical_history
    )