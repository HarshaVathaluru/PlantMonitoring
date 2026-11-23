"""PlantGuard maintenance event schemas.

Pydantic models with real types, required/optional fields, enums, constraints,
and cross-field validators. These models flow through the entire pipeline:
intake -> tools -> graph -> agents -> API.
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EventSource(str, Enum):
    SENSOR_ALERT = "sensor_alert"
    OPERATOR_LOG = "operator_log"
    SCADA = "scada"
    MAINTENANCE_SYSTEM = "maintenance_system"
    MANUAL_ENTRY = "manual_entry"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class UncertaintyLevel(str, Enum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    UNCERTAIN = "uncertain"
    CONTRADICTORY = "contradictory"
    INVALID = "invalid"


class AssetCriticality(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class ApprovalRequiredReason(str, Enum):
    ENERGY_ISOLATION_REQUIRED = "ENERGY_ISOLATION_REQUIRED"
    SAFETY_CRITICAL_PERMIT_REQUIRED = "SAFETY_CRITICAL_PERMIT_REQUIRED"
    PO_VALUE_ABOVE_AUTO_LIMIT = "PO_VALUE_ABOVE_AUTO_LIMIT"
    PRODUCTION_IMPACT_HIGH = "PRODUCTION_IMPACT_HIGH"
    EQUIPMENT_CRITICALITY_A = "EQUIPMENT_CRITICALITY_A"


class WorkOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class RecommendedAction(str, Enum):
    INSPECTION = "INSPECTION"
    LUBRICATION = "LUBRICATION"
    BEARING_REPLACEMENT = "BEARING_REPLACEMENT"
    ALIGNMENT = "ALIGNMENT"
    CALIBRATION = "CALIBRATION"
    EMERGENCY_STOP = "EMERGENCY_STOP"



class SensorReadings(BaseModel):
    """Sensor readings with physical plausibility constraints."""
    vibration_mm_s: Optional[float] = Field(None, description="Vibration RMS in mm/s")
    temp_c: Optional[float] = Field(None, description="Surface temperature in Celsius")
    pressure_bar: Optional[float] = Field(None, description="Operating pressure in bar")
    current_a: Optional[float] = Field(None, description="Motor current in amperes")

    @field_validator("vibration_mm_s")
    @classmethod
    def validate_vibration(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Vibration cannot be negative")
        return v


class DataQualityFlags(BaseModel):
    """Flags raised during intake validation."""
    has_impossible_readings: bool = False
    has_contradictory_evidence: bool = False
    has_missing_required_fields: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    plausibility_issues: List[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    """Ground truth labels from intake data (for evaluation, never runtime decisions)."""
    priority: Optional[str] = None
    probable_fault: Optional[str] = None
    safety_critical: Optional[bool] = None
    requires_permit: Optional[bool] = None
    missing_fields: List[str] = Field(default_factory=list)


class MaintenanceEvent(BaseModel):
    """
    Validated maintenance event produced by the intake agent.

    This is the primary typed data structure flowing through the PlantGuard pipeline.
    Downstream nodes consume this validated object, never raw model text.
    """
    # ── Identity ──
    event_id: str = Field(..., description="Unique event identifier")
    source: EventSource = Field(..., description="Source system of the event")
    received_at: datetime = Field(..., description="Timestamp when event was received")

    # ── Raw input ──
    raw_text: str = Field(..., min_length=1, description="Original alert/log text")

    # ── Asset identification ──
    asset_code: Optional[str] = Field(None, description="Asset class code e.g. CNC-MILL")
    asset_tag: Optional[str] = Field(None, description="Specific machine tag e.g. VPW-HYD-PRESS-02")

    # ── Parsed fields ──
    readings: SensorReadings = Field(default_factory=SensorReadings)
    description: str = Field(default="", description="Parsed event description")
    fault_type: Optional[str] = Field(None, description="Identified or suspected fault type")
    severity: RiskLevel = Field(default=RiskLevel.UNKNOWN, description="Assessed risk level")
    priority: Optional[Priority] = Field(None, description="Assigned priority")

    # ── Uncertainty and quality ──
    uncertainty: UncertaintyLevel = Field(
        default=UncertaintyLevel.UNCERTAIN,
        description="Confidence level of the parsed data"
    )
    data_quality: DataQualityFlags = Field(default_factory=DataQualityFlags)

    # ── Safety ──
    safety_critical: bool = Field(default=False, description="Whether this event involves safety-critical actions")
    requires_permit: bool = Field(default=False, description="Whether a permit is required")
    requires_human_approval: bool = Field(default=False, description="Whether human approval is needed")

    # ── Ground truth (preserved from intake data for evaluation) ──
    ground_truth: Optional[GroundTruth] = Field(None, description="Preserved ground truth for evaluation")

    # ── Metadata ──
    parsed_by_model: Optional[str] = Field(None, description="Model used for parsing")
    parse_attempts: int = Field(default=1, ge=1, description="Number of parse attempts")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("event_id cannot be empty")
        return v.strip()

    @field_validator("asset_tag")
    @classmethod
    def validate_asset_tag(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
        return v

    @field_validator("asset_code")
    @classmethod
    def validate_asset_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
        return v

    @model_validator(mode="after")
    def cross_field_validation(self) -> "MaintenanceEvent":
        """Cross-field validation for physical plausibility and consistency."""
        from app.config.settings import get_settings
        settings = get_settings()

        warnings = list(self.data_quality.validation_warnings)
        plausibility = list(self.data_quality.plausibility_issues)
        has_impossible = self.data_quality.has_impossible_readings
        missing = list(self.data_quality.missing_fields)

        # Check for missing critical fields and sensor readings
        if not self.asset_tag and not self.asset_code:
            missing.append("asset_identifier")
            self.data_quality.has_missing_required_fields = True

        r = self.readings
        if r.vibration_mm_s is None or r.temp_c is None:
            if r.vibration_mm_s is None:
                missing.append("vibration_mm_s")
            if r.temp_c is None:
                missing.append("temp_c")
            self.data_quality.has_missing_required_fields = True

        # Physical plausibility checks
        r = self.readings
        if r.vibration_mm_s is not None and r.vibration_mm_s > settings.SAFETY_VIBRATION_MAX_MM_S:
            plausibility.append(
                f"Vibration {r.vibration_mm_s} mm/s exceeds physical limit ({settings.SAFETY_VIBRATION_MAX_MM_S})"
            )
            has_impossible = True

        if r.temp_c is not None:
            if r.temp_c < settings.SAFETY_TEMP_MIN_C:
                plausibility.append(
                    f"Temperature {r.temp_c}°C below physical minimum ({settings.SAFETY_TEMP_MIN_C})"
                )
                has_impossible = True
            elif r.temp_c > settings.SAFETY_TEMP_MAX_C:
                plausibility.append(
                    f"Temperature {r.temp_c}°C exceeds physical maximum ({settings.SAFETY_TEMP_MAX_C})"
                )
                has_impossible = True

        if r.pressure_bar is not None and r.pressure_bar < settings.SAFETY_PRESSURE_MIN_BAR:
            plausibility.append(f"Pressure {r.pressure_bar} bar is negative")
            has_impossible = True

        if r.current_a is not None and r.current_a > settings.SAFETY_CURRENT_MAX_A:
            plausibility.append(
                f"Current {r.current_a}A exceeds physical maximum ({settings.SAFETY_CURRENT_MAX_A})"
            )
            has_impossible = True

        # Combined impossible reading detection (e.g., 912 mm/s vibration + -40°C temp)
        if (r.vibration_mm_s is not None and r.vibration_mm_s > settings.SAFETY_VIBRATION_MAX_MM_S
                and r.temp_c is not None and r.temp_c < settings.SAFETY_TEMP_MIN_C):
            plausibility.append(
                "Combined impossible readings: extreme vibration with sub-zero temperature "
                "indicates sensor malfunction or data corruption"
            )
            self.uncertainty = UncertaintyLevel.INVALID

        self.data_quality.validation_warnings = warnings
        self.data_quality.plausibility_issues = plausibility
        self.data_quality.has_impossible_readings = has_impossible
        self.data_quality.missing_fields = missing

        # Auto-flag safety based on severity
        if self.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH) or self.safety_critical:
            self.requires_human_approval = True
            self.safety_critical = True

        return self


class IntakeResult(BaseModel):
    """Result of processing one or more intake records."""
    events: List[MaintenanceEvent] = Field(default_factory=list)
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class RepairAttempt(BaseModel):
    """Tracks a structured output repair attempt."""
    attempt_number: int
    error_message: str
    raw_output: str
    was_repaired: bool = False
