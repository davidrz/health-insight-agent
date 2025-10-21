"""
Domain services for the Health Insight Agent.

This module contains domain services that implement business logic
that doesn't naturally belong to a single entity or value object.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from statistics import mean, median

from .entities import (
    HealthData, VitalSigns, LabResult, Symptom, MedicalHistory,
    VitalType, LabResultType, SeverityLevel, RiskLevel
)
from .value_objects import (
    HealthInsight, RiskAssessment, RiskFactor, Recommendation,
    InsightType, RecommendationType, RecommendationPriority
)


class HealthDataValidationService:
    """Service for validating and enriching health data."""
    
    @staticmethod
    def validate_health_data_completeness(health_data: HealthData) -> Dict[str, bool]:
        """
        Validate the completeness of health data.
        
        Args:
            health_data: The health data to validate
            
        Returns:
            Dictionary indicating completeness of different data sections
        """
        completeness = {
            "has_vitals": health_data.vitals is not None,
            "has_complete_vitals": health_data.has_complete_vitals(),
            "has_lab_results": len(health_data.lab_results) > 0,
            "has_symptoms": len(health_data.symptoms) > 0,
            "has_medical_history": health_data.medical_history is not None,
            "has_complete_medical_history": (
                health_data.medical_history is not None and
                len(health_data.medical_history.conditions) > 0
            )
        }
        
        completeness["overall_complete"] = all([
            completeness["has_complete_vitals"],
            completeness["has_lab_results"],
            completeness["has_medical_history"]
        ])
        
        return completeness
    
    @staticmethod
    def identify_data_quality_issues(health_data: HealthData) -> List[str]:
        """
        Identify potential data quality issues in health data.
        
        Args:
            health_data: The health data to analyze
            
        Returns:
            List of identified data quality issues
        """
        issues = []
        
        # Check for missing critical data
        if not health_data.has_complete_vitals():
            issues.append("Missing essential vital signs")
        
        # Check for inconsistent vital signs
        if health_data.vitals:
            vitals = health_data.vitals
            if (vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic and
                vitals.blood_pressure_systolic <= vitals.blood_pressure_diastolic):
                issues.append("Systolic blood pressure should be higher than diastolic")
        
        # Check for outdated data
        data_age = datetime.utcnow() - health_data.timestamp
        if data_age > timedelta(days=30):
            issues.append("Health data is more than 30 days old")
        
        # Check for abnormal lab results without reference ranges
        for lab_result in health_data.lab_results:
            if (lab_result.reference_range_min is None or 
                lab_result.reference_range_max is None):
                issues.append(f"Missing reference range for {lab_result.test_type.value}")
        
        return issues


class VitalSignsAnalysisService:
    """Service for analyzing vital signs and identifying patterns."""
    
    # Normal ranges for vital signs (adult values)
    NORMAL_RANGES = {
        VitalType.HEART_RATE: (60, 100),
        VitalType.BLOOD_PRESSURE_SYSTOLIC: (90, 140),
        VitalType.BLOOD_PRESSURE_DIASTOLIC: (60, 90),
        VitalType.TEMPERATURE: (36.1, 37.2),
        VitalType.RESPIRATORY_RATE: (12, 20),
        VitalType.OXYGEN_SATURATION: (95.0, 100.0)
    }
    
    @classmethod
    def analyze_vital_signs(cls, vitals: VitalSigns) -> Dict[str, Any]:
        """
        Analyze vital signs and identify abnormalities.
        
        Args:
            vitals: The vital signs to analyze
            
        Returns:
            Analysis results including abnormalities and severity
        """
        analysis = {
            "abnormalities": [],
            "severity": SeverityLevel.MILD,
            "requires_attention": False
        }
        
        # Check each vital sign against normal ranges
        vital_checks = [
            (VitalType.HEART_RATE, vitals.heart_rate),
            (VitalType.BLOOD_PRESSURE_SYSTOLIC, vitals.blood_pressure_systolic),
            (VitalType.BLOOD_PRESSURE_DIASTOLIC, vitals.blood_pressure_diastolic),
            (VitalType.TEMPERATURE, vitals.temperature),
            (VitalType.RESPIRATORY_RATE, vitals.respiratory_rate),
            (VitalType.OXYGEN_SATURATION, vitals.oxygen_saturation)
        ]
        
        severe_abnormalities = 0
        
        for vital_type, value in vital_checks:
            if value is not None and vital_type in cls.NORMAL_RANGES:
                min_val, max_val = cls.NORMAL_RANGES[vital_type]
                
                if value < min_val or value > max_val:
                    deviation = cls._calculate_deviation_severity(value, min_val, max_val)
                    analysis["abnormalities"].append({
                        "vital": vital_type.value,
                        "value": value,
                        "normal_range": (min_val, max_val),
                        "severity": deviation
                    })
                    
                    if deviation in [SeverityLevel.SEVERE, SeverityLevel.CRITICAL]:
                        severe_abnormalities += 1
        
        # Determine overall severity
        if severe_abnormalities > 0:
            analysis["severity"] = SeverityLevel.SEVERE
            analysis["requires_attention"] = True
        elif len(analysis["abnormalities"]) >= 2:
            analysis["severity"] = SeverityLevel.MODERATE
            analysis["requires_attention"] = True
        elif len(analysis["abnormalities"]) > 0:
            analysis["severity"] = SeverityLevel.MILD
        
        return analysis
    
    @staticmethod
    def _calculate_deviation_severity(value: float, min_val: float, max_val: float) -> SeverityLevel:
        """Calculate the severity of deviation from normal range."""
        if value < min_val:
            deviation_percent = (min_val - value) / min_val
        else:
            deviation_percent = (value - max_val) / max_val
        
        if deviation_percent >= 0.5:  # 50% or more deviation
            return SeverityLevel.CRITICAL
        elif deviation_percent >= 0.3:  # 30-49% deviation
            return SeverityLevel.SEVERE
        elif deviation_percent >= 0.15:  # 15-29% deviation
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD


class RiskAssessmentService:
    """Service for assessing health risks based on health data."""
    
    @staticmethod
    def assess_cardiovascular_risk(health_data: HealthData) -> RiskFactor:
        """
        Assess cardiovascular risk based on health data.
        
        Args:
            health_data: The health data to analyze
            
        Returns:
            Cardiovascular risk factor assessment
        """
        risk_score = 0.0
        contributing_factors = []
        
        # Analyze vital signs
        if health_data.vitals:
            vitals = health_data.vitals
            
            # High blood pressure
            if (vitals.blood_pressure_systolic and vitals.blood_pressure_systolic > 140):
                risk_score += 0.3
                contributing_factors.append("Elevated systolic blood pressure")
            
            if (vitals.blood_pressure_diastolic and vitals.blood_pressure_diastolic > 90):
                risk_score += 0.2
                contributing_factors.append("Elevated diastolic blood pressure")
            
            # Abnormal heart rate
            if vitals.heart_rate and (vitals.heart_rate > 100 or vitals.heart_rate < 50):
                risk_score += 0.1
                contributing_factors.append("Abnormal heart rate")
        
        # Analyze lab results
        for lab_result in health_data.lab_results:
            if lab_result.test_type == LabResultType.CHOLESTEROL_TOTAL and lab_result.value > 240:
                risk_score += 0.25
                contributing_factors.append("High total cholesterol")
            elif lab_result.test_type == LabResultType.CHOLESTEROL_LDL and lab_result.value > 160:
                risk_score += 0.2
                contributing_factors.append("High LDL cholesterol")
        
        # Analyze medical history
        if health_data.medical_history:
            cardiovascular_conditions = [
                "hypertension", "diabetes", "heart disease", "stroke", "atherosclerosis"
            ]
            for condition in health_data.medical_history.conditions:
                if any(cv_condition in condition.lower() for cv_condition in cardiovascular_conditions):
                    risk_score += 0.3
                    contributing_factors.append(f"History of {condition}")
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = RiskLevel.VERY_HIGH
        elif risk_score >= 0.5:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.3:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW
        
        mitigation_strategies = []
        if risk_score > 0.3:
            mitigation_strategies.extend([
                "Regular cardiovascular exercise",
                "Heart-healthy diet low in saturated fats",
                "Regular blood pressure monitoring",
                "Stress management techniques"
            ])
        
        return RiskFactor(
            name="Cardiovascular Disease",
            risk_level=risk_level,
            probability=min(risk_score, 1.0),
            contributing_factors=contributing_factors,
            mitigation_strategies=mitigation_strategies
        )
    
    @staticmethod
    def assess_diabetes_risk(health_data: HealthData) -> RiskFactor:
        """
        Assess diabetes risk based on health data.
        
        Args:
            health_data: The health data to analyze
            
        Returns:
            Diabetes risk factor assessment
        """
        risk_score = 0.0
        contributing_factors = []
        
        # Analyze lab results
        for lab_result in health_data.lab_results:
            if lab_result.test_type == LabResultType.BLOOD_GLUCOSE:
                if lab_result.value >= 126:  # Fasting glucose >= 126 mg/dL
                    risk_score += 0.5
                    contributing_factors.append("Elevated fasting glucose")
                elif lab_result.value >= 100:  # Pre-diabetic range
                    risk_score += 0.3
                    contributing_factors.append("Pre-diabetic glucose levels")
            
            elif lab_result.test_type == LabResultType.HEMOGLOBIN_A1C:
                if lab_result.value >= 6.5:  # Diabetic range
                    risk_score += 0.6
                    contributing_factors.append("Elevated HbA1c")
                elif lab_result.value >= 5.7:  # Pre-diabetic range
                    risk_score += 0.3
                    contributing_factors.append("Pre-diabetic HbA1c")
        
        # Analyze medical history
        if health_data.medical_history:
            diabetes_related = ["diabetes", "insulin resistance", "metabolic syndrome"]
            for condition in health_data.medical_history.conditions:
                if any(diabetes_term in condition.lower() for diabetes_term in diabetes_related):
                    risk_score += 0.4
                    contributing_factors.append(f"History of {condition}")
        
        # Determine risk level
        if risk_score >= 0.6:
            risk_level = RiskLevel.VERY_HIGH
        elif risk_score >= 0.4:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.2:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW
        
        mitigation_strategies = []
        if risk_score > 0.2:
            mitigation_strategies.extend([
                "Maintain healthy weight",
                "Regular physical activity",
                "Balanced diet with controlled carbohydrates",
                "Regular glucose monitoring"
            ])
        
        return RiskFactor(
            name="Type 2 Diabetes",
            risk_level=risk_level,
            probability=min(risk_score, 1.0),
            contributing_factors=contributing_factors,
            mitigation_strategies=mitigation_strategies
        )


class RecommendationService:
    """Service for generating health recommendations based on analysis."""
    
    @staticmethod
    def generate_vital_signs_recommendations(
        vitals_analysis: Dict[str, Any]
    ) -> List[Recommendation]:
        """
        Generate recommendations based on vital signs analysis.
        
        Args:
            vitals_analysis: Results from vital signs analysis
            
        Returns:
            List of recommendations for addressing vital sign abnormalities
        """
        recommendations = []
        
        if not vitals_analysis.get("abnormalities"):
            return recommendations
        
        severity = vitals_analysis.get("severity", SeverityLevel.MILD)
        
        # Determine priority based on severity
        if severity == SeverityLevel.CRITICAL:
            priority = RecommendationPriority.URGENT
            timeframe = "immediately"
        elif severity == SeverityLevel.SEVERE:
            priority = RecommendationPriority.HIGH
            timeframe = "within 24 hours"
        elif severity == SeverityLevel.MODERATE:
            priority = RecommendationPriority.MEDIUM
            timeframe = "within 1 week"
        else:
            priority = RecommendationPriority.LOW
            timeframe = "within 2 weeks"
        
        # Generate specific recommendations based on abnormalities
        for abnormality in vitals_analysis["abnormalities"]:
            vital_type = abnormality["vital"]
            
            if vital_type in ["blood_pressure_systolic", "blood_pressure_diastolic"]:
                recommendations.append(Recommendation(
                    recommendation_type=RecommendationType.MEDICAL_CONSULTATION,
                    priority=priority,
                    title="Blood Pressure Evaluation",
                    description="Consult with healthcare provider for blood pressure management",
                    rationale=f"Abnormal {vital_type}: {abnormality['value']}",
                    timeframe=timeframe
                ))
            
            elif vital_type == "heart_rate":
                recommendations.append(Recommendation(
                    recommendation_type=RecommendationType.MEDICAL_CONSULTATION,
                    priority=priority,
                    title="Cardiac Evaluation",
                    description="Evaluate abnormal heart rate with healthcare provider",
                    rationale=f"Heart rate outside normal range: {abnormality['value']} bpm",
                    timeframe=timeframe
                ))
        
        return recommendations
    
    @staticmethod
    def generate_risk_based_recommendations(
        risk_factors: List[RiskFactor]
    ) -> List[Recommendation]:
        """
        Generate recommendations based on identified risk factors.
        
        Args:
            risk_factors: List of identified risk factors
            
        Returns:
            List of recommendations for risk mitigation
        """
        recommendations = []
        
        for risk_factor in risk_factors:
            if risk_factor.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                priority = RecommendationPriority.HIGH
                timeframe = "within 1 week"
            elif risk_factor.risk_level == RiskLevel.MODERATE:
                priority = RecommendationPriority.MEDIUM
                timeframe = "within 2 weeks"
            else:
                priority = RecommendationPriority.LOW
                timeframe = "within 1 month"
            
            # Generate lifestyle recommendations
            for strategy in risk_factor.mitigation_strategies:
                recommendations.append(Recommendation(
                    recommendation_type=RecommendationType.LIFESTYLE_CHANGE,
                    priority=priority,
                    title=f"Risk Mitigation: {strategy}",
                    description=f"Implement {strategy.lower()} to reduce {risk_factor.name} risk",
                    rationale=f"High risk identified for {risk_factor.name}",
                    timeframe=timeframe
                ))
        
        return recommendations