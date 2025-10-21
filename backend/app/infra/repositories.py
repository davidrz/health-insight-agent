"""
Concrete repository implementations for Health Insight Agent.

This module provides SQLAlchemy-based implementations of the repository
interfaces defined in the domain layer.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, NoResultFound

from ..domain.entities import HealthData, VitalSigns, LabResult, Symptom, MedicalHistory
from ..domain.value_objects import InsightReport
from ..domain.repositories import (
    HealthDataRepository, InsightReportRepository, PatientRepository,
    RepositoryError, NotFoundError, DuplicateError, ValidationError
)
from .models import Patient, HealthRecord, InsightReport as InsightReportModel
from .cache import cache_manager

logger = logging.getLogger(__name__)


class SQLAlchemyHealthDataRepository(HealthDataRepository):
    """SQLAlchemy implementation of HealthDataRepository."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, health_data: HealthData) -> HealthData:
        """Save health data to the database."""
        try:
            # Ensure patient exists
            patient_repo = SQLAlchemyPatientRepository(self.session)
            if not await patient_repo.patient_exists(health_data.patient_id):
                await patient_repo.create_patient(health_data.patient_id)
            
            # Get patient UUID
            patient = await self._get_patient_by_external_id(health_data.patient_id)
            
            # Serialize health data
            serialized_data = self._serialize_health_data(health_data)
            
            # Create health record
            health_record = HealthRecord(
                patient_id=patient.id,
                data_type="complete_health_data",
                raw_data=serialized_data,
                timestamp=health_data.timestamp
            )
            
            self.session.add(health_record)
            await self.session.commit()
            await self.session.refresh(health_record)
            
            # Invalidate cache
            await cache_manager.invalidate_patient_cache(health_data.patient_id)
            
            logger.info(f"Saved health data for patient {health_data.patient_id}")
            return health_data
            
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error saving health data: {e}")
            raise DuplicateError(f"Health data already exists: {e}")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving health data: {e}")
            raise RepositoryError(f"Failed to save health data: {e}")
    
    async def get_by_id(self, data_id: UUID) -> Optional[HealthData]:
        """Retrieve health data by ID."""
        try:
            stmt = select(HealthRecord).where(HealthRecord.id == data_id)
            result = await self.session.execute(stmt)
            health_record = result.scalar_one_or_none()
            
            if not health_record:
                return None
            
            # Get patient external ID
            patient = await self.session.get(Patient, health_record.patient_id)
            if not patient:
                return None
            
            return self._deserialize_health_data(health_record.raw_data, patient.external_id)
            
        except Exception as e:
            logger.error(f"Error retrieving health data by ID {data_id}: {e}")
            raise RepositoryError(f"Failed to retrieve health data: {e}")
    
    async def get_by_patient_id(self, patient_id: str) -> List[HealthData]:
        """Retrieve all health data for a patient."""
        try:
            # Check cache first
            cache_key = f"health_data:{patient_id}"
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                return [self._deserialize_health_data(data, patient_id) for data in cached_data]
            
            # Get patient
            patient = await self._get_patient_by_external_id(patient_id)
            if not patient:
                return []
            
            # Query health records
            stmt = (
                select(HealthRecord)
                .where(HealthRecord.patient_id == patient.id)
                .order_by(desc(HealthRecord.timestamp))
            )
            result = await self.session.execute(stmt)
            health_records = result.scalars().all()
            
            # Deserialize data
            health_data_list = []
            serialized_list = []
            for record in health_records:
                health_data = self._deserialize_health_data(record.raw_data, patient_id)
                health_data_list.append(health_data)
                serialized_list.append(record.raw_data)
            
            # Cache the results
            await cache_manager.set(cache_key, serialized_list, ttl=1800)  # 30 minutes
            
            return health_data_list
            
        except Exception as e:
            logger.error(f"Error retrieving health data for patient {patient_id}: {e}")
            raise RepositoryError(f"Failed to retrieve health data: {e}")
    
    async def get_by_patient_id_and_date_range(
        self, 
        patient_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[HealthData]:
        """Retrieve health data for a patient within a date range."""
        try:
            # Get patient
            patient = await self._get_patient_by_external_id(patient_id)
            if not patient:
                return []
            
            # Query health records within date range
            stmt = (
                select(HealthRecord)
                .where(
                    and_(
                        HealthRecord.patient_id == patient.id,
                        HealthRecord.timestamp >= start_date,
                        HealthRecord.timestamp <= end_date
                    )
                )
                .order_by(desc(HealthRecord.timestamp))
            )
            result = await self.session.execute(stmt)
            health_records = result.scalars().all()
            
            # Deserialize data
            return [
                self._deserialize_health_data(record.raw_data, patient_id)
                for record in health_records
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving health data for patient {patient_id} in date range: {e}")
            raise RepositoryError(f"Failed to retrieve health data: {e}")
    
    async def update(self, health_data: HealthData) -> HealthData:
        """Update existing health data."""
        try:
            # Find existing record
            stmt = select(HealthRecord).where(HealthRecord.id == health_data.data_id)
            result = await self.session.execute(stmt)
            health_record = result.scalar_one_or_none()
            
            if not health_record:
                raise NotFoundError(f"Health data with ID {health_data.data_id} not found")
            
            # Update record
            serialized_data = self._serialize_health_data(health_data)
            health_record.raw_data = serialized_data
            health_record.timestamp = health_data.timestamp
            
            await self.session.commit()
            
            # Invalidate cache
            await cache_manager.invalidate_patient_cache(health_data.patient_id)
            
            logger.info(f"Updated health data {health_data.data_id}")
            return health_data
            
        except NoResultFound:
            raise NotFoundError(f"Health data with ID {health_data.data_id} not found")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating health data: {e}")
            raise RepositoryError(f"Failed to update health data: {e}")
    
    async def delete(self, data_id: UUID) -> bool:
        """Delete health data."""
        try:
            # Get the record first to get patient_id for cache invalidation
            stmt = select(HealthRecord).where(HealthRecord.id == data_id)
            result = await self.session.execute(stmt)
            health_record = result.scalar_one_or_none()
            
            if not health_record:
                return False
            
            # Get patient external ID for cache invalidation
            patient = await self.session.get(Patient, health_record.patient_id)
            
            # Delete record
            await self.session.delete(health_record)
            await self.session.commit()
            
            # Invalidate cache
            if patient:
                await cache_manager.invalidate_patient_cache(patient.external_id)
            
            logger.info(f"Deleted health data {data_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting health data: {e}")
            raise RepositoryError(f"Failed to delete health data: {e}")
    
    async def exists(self, data_id: UUID) -> bool:
        """Check if health data exists."""
        try:
            stmt = select(func.count(HealthRecord.id)).where(HealthRecord.id == data_id)
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking health data existence: {e}")
            return False
    
    async def _get_patient_by_external_id(self, external_id: str) -> Optional[Patient]:
        """Get patient by external ID."""
        stmt = select(Patient).where(Patient.external_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    def _serialize_health_data(self, health_data: HealthData) -> Dict[str, Any]:
        """Serialize HealthData to JSON-compatible dict."""
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
        """Deserialize JSON dict to HealthData."""
        from ..domain.entities import LabResultType, SeverityLevel
        
        # Parse vitals
        vitals = None
        if "vitals" in data:
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
        if "lab_results" in data:
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
        if "symptoms" in data:
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
        if "medical_history" in data:
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

class SQLAlchemyInsightReportRepository(InsightReportRepository):
    """SQLAlchemy implementation of InsightReportRepository."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, report: InsightReport) -> InsightReport:
        """Save insight report to the database."""
        try:
            # Ensure patient exists
            patient_repo = SQLAlchemyPatientRepository(self.session)
            if not await patient_repo.patient_exists(report.patient_id):
                await patient_repo.create_patient(report.patient_id)
            
            # Get patient UUID
            patient = await self._get_patient_by_external_id(report.patient_id)
            
            # Serialize report data
            serialized_data = self._serialize_insight_report(report)
            
            # Create insight report record
            insight_report = InsightReportModel(
                id=report.report_id,
                patient_id=patient.id,
                report_data=serialized_data,
                confidence_score=report.confidence_score,
                status="generated"
            )
            
            self.session.add(insight_report)
            await self.session.commit()
            await self.session.refresh(insight_report)
            
            # Invalidate cache
            await cache_manager.invalidate_patient_cache(report.patient_id)
            
            logger.info(f"Saved insight report for patient {report.patient_id}")
            return report
            
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error saving insight report: {e}")
            raise DuplicateError(f"Insight report already exists: {e}")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving insight report: {e}")
            raise RepositoryError(f"Failed to save insight report: {e}")
    
    async def get_by_id(self, report_id: UUID) -> Optional[InsightReport]:
        """Retrieve insight report by ID."""
        try:
            stmt = select(InsightReportModel).where(InsightReportModel.id == report_id)
            result = await self.session.execute(stmt)
            report_model = result.scalar_one_or_none()
            
            if not report_model:
                return None
            
            # Get patient external ID
            patient = await self.session.get(Patient, report_model.patient_id)
            if not patient:
                return None
            
            return self._deserialize_insight_report(report_model.report_data, patient.external_id, report_id)
            
        except Exception as e:
            logger.error(f"Error retrieving insight report by ID {report_id}: {e}")
            raise RepositoryError(f"Failed to retrieve insight report: {e}")
    
    async def get_by_patient_id(self, patient_id: str) -> List[InsightReport]:
        """Retrieve all insight reports for a patient."""
        try:
            # Check cache first
            cache_key = f"reports:{patient_id}"
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                return [
                    self._deserialize_insight_report(data["report_data"], patient_id, UUID(data["report_id"]))
                    for data in cached_data
                ]
            
            # Get patient
            patient = await self._get_patient_by_external_id(patient_id)
            if not patient:
                return []
            
            # Query insight reports
            stmt = (
                select(InsightReportModel)
                .where(InsightReportModel.patient_id == patient.id)
                .order_by(desc(InsightReportModel.created_at))
            )
            result = await self.session.execute(stmt)
            report_models = result.scalars().all()
            
            # Deserialize reports
            reports = []
            serialized_list = []
            for model in report_models:
                report = self._deserialize_insight_report(model.report_data, patient_id, model.id)
                reports.append(report)
                serialized_list.append({
                    "report_id": str(model.id),
                    "report_data": model.report_data
                })
            
            # Cache the results
            await cache_manager.set(cache_key, serialized_list, ttl=3600)  # 1 hour
            
            return reports
            
        except Exception as e:
            logger.error(f"Error retrieving insight reports for patient {patient_id}: {e}")
            raise RepositoryError(f"Failed to retrieve insight reports: {e}")
    
    async def get_latest_by_patient_id(self, patient_id: str) -> Optional[InsightReport]:
        """Retrieve the most recent insight report for a patient."""
        try:
            # Get patient
            patient = await self._get_patient_by_external_id(patient_id)
            if not patient:
                return None
            
            # Query latest insight report
            stmt = (
                select(InsightReportModel)
                .where(InsightReportModel.patient_id == patient.id)
                .order_by(desc(InsightReportModel.created_at))
                .limit(1)
            )
            result = await self.session.execute(stmt)
            report_model = result.scalar_one_or_none()
            
            if not report_model:
                return None
            
            return self._deserialize_insight_report(report_model.report_data, patient_id, report_model.id)
            
        except Exception as e:
            logger.error(f"Error retrieving latest insight report for patient {patient_id}: {e}")
            raise RepositoryError(f"Failed to retrieve latest insight report: {e}")
    
    async def get_by_patient_id_and_date_range(
        self, 
        patient_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[InsightReport]:
        """Retrieve insight reports for a patient within a date range."""
        try:
            # Get patient
            patient = await self._get_patient_by_external_id(patient_id)
            if not patient:
                return []
            
            # Query insight reports within date range
            stmt = (
                select(InsightReportModel)
                .where(
                    and_(
                        InsightReportModel.patient_id == patient.id,
                        InsightReportModel.created_at >= start_date,
                        InsightReportModel.created_at <= end_date
                    )
                )
                .order_by(desc(InsightReportModel.created_at))
            )
            result = await self.session.execute(stmt)
            report_models = result.scalars().all()
            
            # Deserialize reports
            return [
                self._deserialize_insight_report(model.report_data, patient_id, model.id)
                for model in report_models
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving insight reports for patient {patient_id} in date range: {e}")
            raise RepositoryError(f"Failed to retrieve insight reports: {e}")
    
    async def update(self, report: InsightReport) -> InsightReport:
        """Update existing insight report."""
        try:
            # Find existing record
            stmt = select(InsightReportModel).where(InsightReportModel.id == report.report_id)
            result = await self.session.execute(stmt)
            report_model = result.scalar_one_or_none()
            
            if not report_model:
                raise NotFoundError(f"Insight report with ID {report.report_id} not found")
            
            # Update record
            serialized_data = self._serialize_insight_report(report)
            report_model.report_data = serialized_data
            report_model.confidence_score = report.confidence_score
            
            await self.session.commit()
            
            # Invalidate cache
            await cache_manager.invalidate_patient_cache(report.patient_id)
            
            logger.info(f"Updated insight report {report.report_id}")
            return report
            
        except NoResultFound:
            raise NotFoundError(f"Insight report with ID {report.report_id} not found")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating insight report: {e}")
            raise RepositoryError(f"Failed to update insight report: {e}")
    
    async def delete(self, report_id: UUID) -> bool:
        """Delete insight report."""
        try:
            # Get the record first to get patient_id for cache invalidation
            stmt = select(InsightReportModel).where(InsightReportModel.id == report_id)
            result = await self.session.execute(stmt)
            report_model = result.scalar_one_or_none()
            
            if not report_model:
                return False
            
            # Get patient external ID for cache invalidation
            patient = await self.session.get(Patient, report_model.patient_id)
            
            # Delete record
            await self.session.delete(report_model)
            await self.session.commit()
            
            # Invalidate cache
            if patient:
                await cache_manager.invalidate_patient_cache(patient.external_id)
            
            logger.info(f"Deleted insight report {report_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting insight report: {e}")
            raise RepositoryError(f"Failed to delete insight report: {e}")
    
    async def get_reports_by_confidence_threshold(
        self, 
        min_confidence: float
    ) -> List[InsightReport]:
        """Retrieve insight reports with confidence above a threshold."""
        try:
            # Query reports with high confidence
            stmt = (
                select(InsightReportModel)
                .where(InsightReportModel.confidence_score >= min_confidence)
                .order_by(desc(InsightReportModel.confidence_score))
            )
            result = await self.session.execute(stmt)
            report_models = result.scalars().all()
            
            # Deserialize reports
            reports = []
            for model in report_models:
                # Get patient external ID
                patient = await self.session.get(Patient, model.patient_id)
                if patient:
                    report = self._deserialize_insight_report(model.report_data, patient.external_id, model.id)
                    reports.append(report)
            
            return reports
            
        except Exception as e:
            logger.error(f"Error retrieving high confidence reports: {e}")
            raise RepositoryError(f"Failed to retrieve high confidence reports: {e}")
    
    async def _get_patient_by_external_id(self, external_id: str) -> Optional[Patient]:
        """Get patient by external ID."""
        stmt = select(Patient).where(Patient.external_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    def _serialize_insight_report(self, report: InsightReport) -> Dict[str, Any]:
        """Serialize InsightReport to JSON-compatible dict."""
        data = {
            "report_id": str(report.report_id),
            "patient_id": report.patient_id,
            "confidence_score": report.confidence_score,
            "generated_at": report.generated_at.isoformat(),
            "metadata": report.metadata,
        }
        
        # Serialize insights
        if report.insights:
            data["insights"] = [
                {
                    "insight_type": insight.insight_type.value,
                    "title": insight.title,
                    "description": insight.description,
                    "confidence_score": insight.confidence_score,
                    "supporting_data": insight.supporting_data,
                    "generated_at": insight.generated_at.isoformat(),
                }
                for insight in report.insights
            ]
        
        # Serialize risk assessment
        if report.risk_assessment:
            risk_data = {
                "overall_risk_level": report.risk_assessment.overall_risk_level.value,
                "assessment_summary": report.risk_assessment.assessment_summary,
                "confidence_score": report.risk_assessment.confidence_score,
                "assessed_at": report.risk_assessment.assessed_at.isoformat(),
            }
            
            if report.risk_assessment.risk_factors:
                risk_data["risk_factors"] = [
                    {
                        "name": factor.name,
                        "risk_level": factor.risk_level.value,
                        "probability": factor.probability,
                        "contributing_factors": factor.contributing_factors,
                        "mitigation_strategies": factor.mitigation_strategies,
                    }
                    for factor in report.risk_assessment.risk_factors
                ]
            
            data["risk_assessment"] = risk_data
        
        # Serialize recommendations
        if report.recommendations:
            data["recommendations"] = [
                {
                    "recommendation_type": rec.recommendation_type.value,
                    "priority": rec.priority.value,
                    "title": rec.title,
                    "description": rec.description,
                    "rationale": rec.rationale,
                    "expected_outcome": rec.expected_outcome,
                    "timeframe": rec.timeframe,
                    "created_at": rec.created_at.isoformat(),
                }
                for rec in report.recommendations
            ]
        
        return data
    
    def _deserialize_insight_report(
        self, 
        data: Dict[str, Any], 
        patient_id: str, 
        report_id: UUID
    ) -> InsightReport:
        """Deserialize JSON dict to InsightReport."""
        from ..domain.value_objects import (
            HealthInsight, InsightType, RiskAssessment, RiskFactor, 
            Recommendation, RecommendationType, RecommendationPriority
        )
        from ..domain.entities import RiskLevel
        
        # Parse insights
        insights = []
        if "insights" in data:
            for insight_data in data["insights"]:
                insight = HealthInsight(
                    insight_type=InsightType(insight_data["insight_type"]),
                    title=insight_data["title"],
                    description=insight_data["description"],
                    confidence_score=insight_data["confidence_score"],
                    supporting_data=insight_data.get("supporting_data", {}),
                    generated_at=datetime.fromisoformat(insight_data["generated_at"]),
                )
                insights.append(insight)
        
        # Parse risk assessment
        risk_assessment = None
        if "risk_assessment" in data:
            risk_data = data["risk_assessment"]
            
            # Parse risk factors
            risk_factors = []
            if "risk_factors" in risk_data:
                for factor_data in risk_data["risk_factors"]:
                    factor = RiskFactor(
                        name=factor_data["name"],
                        risk_level=RiskLevel(factor_data["risk_level"]),
                        probability=factor_data["probability"],
                        contributing_factors=factor_data.get("contributing_factors", []),
                        mitigation_strategies=factor_data.get("mitigation_strategies", []),
                    )
                    risk_factors.append(factor)
            
            risk_assessment = RiskAssessment(
                overall_risk_level=RiskLevel(risk_data["overall_risk_level"]),
                risk_factors=risk_factors,
                assessment_summary=risk_data.get("assessment_summary", ""),
                confidence_score=risk_data.get("confidence_score", 0.0),
                assessed_at=datetime.fromisoformat(risk_data["assessed_at"]),
            )
        
        # Parse recommendations
        recommendations = []
        if "recommendations" in data:
            for rec_data in data["recommendations"]:
                recommendation = Recommendation(
                    recommendation_type=RecommendationType(rec_data["recommendation_type"]),
                    priority=RecommendationPriority(rec_data["priority"]),
                    title=rec_data["title"],
                    description=rec_data["description"],
                    rationale=rec_data["rationale"],
                    expected_outcome=rec_data.get("expected_outcome"),
                    timeframe=rec_data.get("timeframe"),
                    created_at=datetime.fromisoformat(rec_data["created_at"]),
                )
                recommendations.append(recommendation)
        
        return InsightReport(
            report_id=report_id,
            patient_id=patient_id,
            insights=insights,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            confidence_score=data.get("confidence_score", 0.0),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            metadata=data.get("metadata", {}),
        )


class SQLAlchemyPatientRepository(PatientRepository):
    """SQLAlchemy implementation of PatientRepository."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_patient(self, patient_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Create a new patient record."""
        try:
            patient = Patient(
                external_id=patient_id,
                patient_metadata=metadata or {}
            )
            
            self.session.add(patient)
            await self.session.commit()
            await self.session.refresh(patient)
            
            logger.info(f"Created patient {patient_id}")
            return True
            
        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(f"Patient {patient_id} already exists: {e}")
            raise DuplicateError(f"Patient {patient_id} already exists")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating patient: {e}")
            raise RepositoryError(f"Failed to create patient: {e}")
    
    async def patient_exists(self, patient_id: str) -> bool:
        """Check if a patient exists."""
        try:
            stmt = select(func.count(Patient.id)).where(Patient.external_id == patient_id)
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking patient existence: {e}")
            return False
    
    async def get_patient_metadata(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a patient."""
        try:
            stmt = select(Patient.patient_metadata).where(Patient.external_id == patient_id)
            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()
            return metadata
            
        except Exception as e:
            logger.error(f"Error retrieving patient metadata: {e}")
            return None
    
    async def update_patient_metadata(
        self, 
        patient_id: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """Update metadata for a patient."""
        try:
            stmt = (
                update(Patient)
                .where(Patient.external_id == patient_id)
                .values(patient_metadata=metadata)
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating patient metadata: {e}")
            raise RepositoryError(f"Failed to update patient metadata: {e}")
    
    async def delete_patient(self, patient_id: str) -> bool:
        """Delete a patient and all associated data."""
        try:
            # Find patient
            stmt = select(Patient).where(Patient.external_id == patient_id)
            result = await self.session.execute(stmt)
            patient = result.scalar_one_or_none()
            
            if not patient:
                return False
            
            # Delete patient (cascade will handle related records)
            await self.session.delete(patient)
            await self.session.commit()
            
            # Invalidate cache
            await cache_manager.invalidate_patient_cache(patient_id)
            
            logger.info(f"Deleted patient {patient_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting patient: {e}")
            raise RepositoryError(f"Failed to delete patient: {e}")
    
    async def list_patients(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None
    ) -> List[str]:
        """List all patient IDs."""
        try:
            stmt = select(Patient.external_id).order_by(Patient.created_at)
            
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            patient_ids = result.scalars().all()
            return list(patient_ids)
            
        except Exception as e:
            logger.error(f"Error listing patients: {e}")
            raise RepositoryError(f"Failed to list patients: {e}")