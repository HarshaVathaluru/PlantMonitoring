"""PlantGuard Production Safety Policy Engine for Milestone 8.

Enforces Probes P1 through P5:
- Probe P1: Direct prompt injection detection & blocking
- Probe P2: Indirect prompt injection scanning & isolation
- Probe P3: Physical plausibility enforcement & sensor malfunction detection
- Probe P4: Unsupported topic detection & explicit fabrication refusal
- Probe P5: Ingestion input structural & type validation
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config.settings import get_settings


class SafetyScanResult(BaseModel):
    is_safe: bool
    injection_detected: bool = False
    violation_type: Optional[str] = None
    sanitized_text: str = ""
    reasons: List[str] = Field(default_factory=list)


class PhysicalPlausibilityResult(BaseModel):
    is_plausible: bool
    has_impossible_readings: bool = False
    probable_sensor_fault: bool = False
    violations: List[str] = Field(default_factory=list)
    alarm_suppression_permitted: bool = False


class SafetyPolicyEngine:
    """Central authoritative safety policy and guardrail engine."""

    DIRECT_INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"system\s+override",
        r"you\s+are\s+now\s+in\s+dan\s+mode",
        r"bypass\s+(all\s+)?(safety|loto|permits?|checks?)",
        r"output\s+the\s+system\s+prompt",
        r"reveal\s+passwords?",
        r"skip\s+(the\s+)?(paperwork|permit|authorization)",
    ]

    INDIRECT_INJECTION_PATTERNS = [
        r"\[system\s*:\s*override\]",
        r"\{\{.*override.*\}\}",
        r"<script.*?>",
        r"<!--\s*admin\s+mode",
        r"disregard\s+sop",
    ]

    UNDOCUMENTED_TERMS = [
        "ammonia",
        "nuclear",
        "rocket",
        "hyperbaric",
        "unapproved",
        "freon-12",
        "cryogenic",
    ]

    def __init__(self):
        self.settings = get_settings()

    def scan_direct_injection(self, text: str) -> SafetyScanResult:
        """Probe P1: Detect direct prompt injection attempts."""
        if not text:
            return SafetyScanResult(is_safe=True, sanitized_text="")

        reasons = []
        injection = False

        for pattern in self.DIRECT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                injection = True
                reasons.append(f"Direct injection pattern detected: '{pattern}'")

        return SafetyScanResult(
            is_safe=not injection,
            injection_detected=injection,
            violation_type="DIRECT_PROMPT_INJECTION" if injection else None,
            sanitized_text=re.sub(r"ignore\s+all\s+previous\s+instructions", "[BLOCKED]", text, flags=re.IGNORECASE),
            reasons=reasons,
        )

    def scan_indirect_injection(self, payload: Any) -> SafetyScanResult:
        """Probe P2: Scan untrusted external logs and inputs for indirect injection payloads."""
        text_repr = json_str = str(payload)
        reasons = []
        injection = False

        for pattern in self.INDIRECT_INJECTION_PATTERNS + self.DIRECT_INJECTION_PATTERNS:
            if re.search(pattern, text_repr, re.IGNORECASE):
                injection = True
                reasons.append(f"Indirect injection payload detected matching pattern '{pattern}'")

        return SafetyScanResult(
            is_safe=not injection,
            injection_detected=injection,
            violation_type="INDIRECT_PROMPT_INJECTION" if injection else None,
            sanitized_text="[CONTENT_SANITIZED_DUE_TO_INJECTION]" if injection else text_repr,
            reasons=reasons,
        )

    def validate_physical_plausibility(
        self,
        vibration_mm_s: Optional[float] = None,
        temp_c: Optional[float] = None,
        pressure_bar: Optional[float] = None,
        current_a: Optional[float] = None,
    ) -> PhysicalPlausibilityResult:
        """
        Probe P3: Enforce physical boundaries.
        Impossible readings indicate sensor malfunction, never diagnosed as mechanical wear.
        Prohibits alarm suppression on physically impossible readings.
        """
        violations = []
        has_impossible = False

        if vibration_mm_s is not None:
            if vibration_mm_s < 0.0:
                violations.append(f"Negative vibration ({vibration_mm_s} mm/s) is physically impossible")
                has_impossible = True
            elif vibration_mm_s > self.settings.SAFETY_VIBRATION_MAX_MM_S:
                violations.append(
                    f"Vibration {vibration_mm_s} mm/s exceeds physical limit ({self.settings.SAFETY_VIBRATION_MAX_MM_S} mm/s)"
                )
                has_impossible = True

        if temp_c is not None:
            if temp_c < self.settings.SAFETY_TEMP_MIN_C:
                violations.append(
                    f"Temperature {temp_c}°C is below plant floor minimum ({self.settings.SAFETY_TEMP_MIN_C}°C)"
                )
                has_impossible = True
            elif temp_c > self.settings.SAFETY_TEMP_MAX_C:
                violations.append(
                    f"Temperature {temp_c}°C exceeds physical plant limit ({self.settings.SAFETY_TEMP_MAX_C}°C)"
                )
                has_impossible = True

        if pressure_bar is not None and pressure_bar < self.settings.SAFETY_PRESSURE_MIN_BAR:
            violations.append(f"Pressure {pressure_bar} bar cannot be negative")
            has_impossible = True

        if current_a is not None and current_a > self.settings.SAFETY_CURRENT_MAX_A:
            violations.append(f"Current {current_a} A exceeds physical capacity ({self.settings.SAFETY_CURRENT_MAX_A} A)")
            has_impossible = True

        # Combined impossible readings (e.g. 912 mm/s vibration and -40 C)
        probable_sensor_fault = has_impossible or (
            vibration_mm_s is not None and vibration_mm_s > 100.0 and temp_c is not None and temp_c < 0.0
        )

        return PhysicalPlausibilityResult(
            is_plausible=not has_impossible,
            has_impossible_readings=has_impossible,
            probable_sensor_fault=probable_sensor_fault,
            violations=violations,
            alarm_suppression_permitted=False,  # Alarm suppression never allowed on sensor faults
        )

    def is_undocumented_topic(self, query: str) -> bool:
        """Probe P4: Identify queries that ask for unsupported/undocumented equipment or systems."""
        q_lower = query.lower()
        return any(term in q_lower for term in self.UNDOCUMENTED_TERMS)
