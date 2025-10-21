"""
SQLAlchemy models for Health Insight Agent database tables.

This module contains the database models that map domain entities
to relational database tables.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, DateTime, Float, Integer, Text, Boolean,
    ForeignKey, Index, CheckConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from .database import Base


class Patient(Base):
    """Patient table for storing patient information."""
    
    __tablename__ = "patients"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    patient_metadata = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    health_records = relationship("HealthRecord", back_populates="patient", cascade="all, delete-orphan")
    insight_reports = relationship("InsightReport", back_populates="patient", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_patients_external_id", "external_id"),
        Index("idx_patients_created_at", "created_at"),
    )
    
    @validates('external_id')
    def validate_external_id(self, key, external_id):
        """Validate external_id is not empty."""
        if not external_id or not external_id.strip():
            raise ValueError("Patient external_id cannot be empty")
        return external_id.strip()
    
    def __repr__(self):
        return f"<Patient(id={self.id}, external_id='{self.external_id}')>"


class HealthRecord(Base):
    """Health records table for storing patient health data."""
    
    __tablename__ = "health_records"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id = Column(PostgresUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    data_type = Column(String(50), nullable=False)  # 'vitals', 'lab_results', 'symptoms', etc.
    raw_data = Column(JSONB, nullable=False)
    processed_data = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    patient = relationship("Patient", back_populates="health_records")
    
    # Indexes
    __table_args__ = (
        Index("idx_health_records_patient_id", "patient_id"),
        Index("idx_health_records_data_type", "data_type"),
        Index("idx_health_records_timestamp", "timestamp"),
        Index("idx_health_records_patient_timestamp", "patient_id", "timestamp"),
        CheckConstraint(
            "data_type IN ('vitals', 'lab_results', 'symptoms', 'medical_history', 'complete_health_data')",
            name="check_valid_data_type"
        ),
    )
    
    @validates('data_type')
    def validate_data_type(self, key, data_type):
        """Validate data_type is one of the allowed values."""
        allowed_types = {'vitals', 'lab_results', 'symptoms', 'medical_history', 'complete_health_data'}
        if data_type not in allowed_types:
            raise ValueError(f"data_type must be one of: {allowed_types}")
        return data_type
    
    @validates('raw_data')
    def validate_raw_data(self, key, raw_data):
        """Validate raw_data is not empty."""
        if not raw_data:
            raise ValueError("raw_data cannot be empty")
        return raw_data
    
    def __repr__(self):
        return f"<HealthRecord(id={self.id}, patient_id={self.patient_id}, data_type='{self.data_type}')>"


class InsightReport(Base):
    """Insight reports table for storing AI-generated health insights."""
    
    __tablename__ = "insight_reports"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id = Column(PostgresUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    report_data = Column(JSONB, nullable=False)
    confidence_score = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="generated")
    report_metadata = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    patient = relationship("Patient", back_populates="insight_reports")
    
    # Indexes
    __table_args__ = (
        Index("idx_insight_reports_patient_id", "patient_id"),
        Index("idx_insight_reports_status", "status"),
        Index("idx_insight_reports_confidence_score", "confidence_score"),
        Index("idx_insight_reports_created_at", "created_at"),
        Index("idx_insight_reports_patient_created", "patient_id", "created_at"),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="check_confidence_score_range"
        ),
        CheckConstraint(
            "status IN ('generated', 'reviewed', 'archived')",
            name="check_valid_status"
        ),
    )
    
    @validates('confidence_score')
    def validate_confidence_score(self, key, confidence_score):
        """Validate confidence_score is between 0.0 and 1.0."""
        if not (0.0 <= confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return confidence_score
    
    @validates('status')
    def validate_status(self, key, status):
        """Validate status is one of the allowed values."""
        allowed_statuses = {'generated', 'reviewed', 'archived'}
        if status not in allowed_statuses:
            raise ValueError(f"status must be one of: {allowed_statuses}")
        return status
    
    @validates('report_data')
    def validate_report_data(self, key, report_data):
        """Validate report_data is not empty."""
        if not report_data:
            raise ValueError("report_data cannot be empty")
        return report_data
    
    def __repr__(self):
        return f"<InsightReport(id={self.id}, patient_id={self.patient_id}, confidence_score={self.confidence_score})>"


class CacheEntry(Base):
    """Cache entries table for storing frequently accessed data."""
    
    __tablename__ = "cache_entries"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    cache_value = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_cache_entries_key", "cache_key"),
        Index("idx_cache_entries_expires_at", "expires_at"),
    )
    
    @validates('cache_key')
    def validate_cache_key(self, key, cache_key):
        """Validate cache_key is not empty."""
        if not cache_key or not cache_key.strip():
            raise ValueError("cache_key cannot be empty")
        return cache_key.strip()
    
    @validates('cache_value')
    def validate_cache_value(self, key, cache_value):
        """Validate cache_value is not empty."""
        if cache_value is None:
            raise ValueError("cache_value cannot be None")
        return cache_value
    
    def is_expired(self) -> bool:
        """Check if the cache entry is expired."""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<CacheEntry(cache_key='{self.cache_key}', expires_at={self.expires_at})>"


class AuditLog(Base):
    """Audit log table for tracking data access and modifications."""
    
    __tablename__ = "audit_logs"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(255), nullable=True)  # Can be null for system operations
    action = Column(String(50), nullable=False)  # 'create', 'read', 'update', 'delete'
    resource_type = Column(String(50), nullable=False)  # 'patient', 'health_record', 'insight_report'
    resource_id = Column(String(255), nullable=False)
    details = Column(JSONB, nullable=True, default=dict)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_resource_id", "resource_id"),
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_user_timestamp", "user_id", "timestamp"),
        CheckConstraint(
            "action IN ('create', 'read', 'update', 'delete')",
            name="check_valid_action"
        ),
    )
    
    @validates('action')
    def validate_action(self, key, action):
        """Validate action is one of the allowed values."""
        allowed_actions = {'create', 'read', 'update', 'delete'}
        if action not in allowed_actions:
            raise ValueError(f"action must be one of: {allowed_actions}")
        return action
    
    @validates('resource_type')
    def validate_resource_type(self, key, resource_type):
        """Validate resource_type is not empty."""
        if not resource_type or not resource_type.strip():
            raise ValueError("resource_type cannot be empty")
        return resource_type.strip()
    
    @validates('resource_id')
    def validate_resource_id(self, key, resource_id):
        """Validate resource_id is not empty."""
        if not resource_id or not resource_id.strip():
            raise ValueError("resource_id cannot be empty")
        return resource_id.strip()
    
    def __repr__(self):
        return f"<AuditLog(action='{self.action}', resource_type='{self.resource_type}', resource_id='{self.resource_id}')>"