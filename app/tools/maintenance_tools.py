"""PlantGuard deterministic operational tools for M2.

Grounded in the 14 mock API tables generated from public industrial datasets
and physical degradation simulator.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


# ── Structured Return Schemas ──

class TelemetryPoint(BaseModel):
    hour_index: int
    vibration_mm_s: float
    temp_c: float
    current_a: float
    pressure_bar: Optional[float] = None


class SensorHistoryResult(BaseModel):
    asset_tag: str
    asset_code: Optional[str] = None
    vibration_warning_mm_s: Optional[float] = None
    vibration_trip_mm_s: Optional[float] = None
    temp_warning_c: Optional[int] = None
    temp_trip_c: Optional[int] = None
    pressure_nominal_bar: Optional[float] = None
    pressure_low_alarm_bar: Optional[float] = None
    points_retrieved: int = 0
    recent_readings: List[TelemetryPoint] = Field(default_factory=list)
    trend_summary: str = ""
    error: Optional[str] = None


class DowntimeCostResult(BaseModel):
    asset_tag: str
    downtime_minutes: int
    hourly_rate_inr: int
    rate_source: str  # "asset_specific" or "class_default"
    total_cost_inr: int
    criticality: str
    safety_risk: str
    environmental_impact: str
    error: Optional[str] = None


class PartInventoryResult(BaseModel):
    part_number: str
    description: str = ""
    asset_code: str = ""
    on_hand: int = 0
    reorder_point: int = 0
    unit_cost_inr: int = 0
    lead_time_days: int = 0
    supplier_tier: str = ""
    supplier_id: Optional[str] = None
    minimum_order_quantity: Optional[int] = None
    is_stock_low: bool = False
    error: Optional[str] = None


class TechnicianSlot(BaseModel):
    technician_id: str
    name: str
    primary_skill: str
    secondary_skill: Optional[str] = None
    skill_level: str
    shift: str
    date: str
    available_hours: int
    loto_authorised: bool
    certifications: List[str] = Field(default_factory=list)


class TechnicianScheduleResult(BaseModel):
    requested_skill: str
    estimated_hours: int
    requested_date: str
    requested_shift: Optional[str] = None
    available_technicians: List[TechnicianSlot] = Field(default_factory=list)
    count: int = 0
    recommendation: Optional[str] = None
    error: Optional[str] = None


# ── Table Data Loader ──

class TableDataLoader:
    """Loads and caches the 14 mock API tables from CSV/JSON."""

    def __init__(self, data_dir: Optional[Path] = None):
        settings = get_settings()
        self.data_dir = data_dir or settings.DATA_DIR / "mock_api"

    @lru_cache(maxsize=16)
    def load_table(self, table_name: str) -> List[Dict[str, Any]]:
        """Load a table from CSV or JSON."""
        json_path = self.data_dir / f"{table_name}.json"
        csv_path = self.data_dir / f"{table_name}.csv"

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif csv_path.exists():
            rows = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert typed fields
                    converted = {}
                    for k, v in row.items():
                        if v == "" or v is None:
                            converted[k] = None
                        elif v.lower() == "true":
                            converted[k] = True
                        elif v.lower() == "false":
                            converted[k] = False
                        else:
                            try:
                                converted[k] = int(v)
                            except ValueError:
                                try:
                                    converted[k] = float(v)
                                except ValueError:
                                    converted[k] = v
                    rows.append(converted)
            return rows
        else:
            logger.error(f"Table file not found: {table_name} in {self.data_dir}")
            return []


@lru_cache(maxsize=1)
def get_table_loader() -> TableDataLoader:
    return TableDataLoader()


# ── Deterministic Tool Implementations ──

def get_sensor_history(asset_tag: str, hours: int = 24) -> SensorHistoryResult:
    """
    Look up hourly sensor history and alarm limits for a specific machine.

    Args:
        asset_tag: Machine identifier e.g. 'VPW-HYD-PRESS-02'
        hours: Number of recent hourly readings to return (default 24, max 720)
    """
    loader = get_table_loader()
    asset_tag = asset_tag.strip().upper()
    hours = min(max(hours, 1), 720)

    # 1. Verify asset exists and get asset_code
    assets = loader.load_table("assets")
    asset = next((a for a in assets if a.get("asset_tag") == asset_tag), None)
    if not asset:
        return SensorHistoryResult(
            asset_tag=asset_tag,
            error=f"Asset tag '{asset_tag}' not found in asset registry",
        )

    asset_code = asset.get("asset_code")

    # 2. Get alarm limits from asset_classes
    classes = loader.load_table("asset_classes")
    aclass = next((c for c in classes if c.get("asset_code") == asset_code), {})

    # 3. Get telemetry records
    telemetry = loader.load_table("telemetry")
    pressure_records = loader.load_table("telemetry_pressure")

    asset_telem = [t for t in telemetry if t.get("asset_tag") == asset_tag]
    # Sort by hour_index descending to get recent
    asset_telem.sort(key=lambda x: x.get("hour_index", 0), reverse=True)
    recent_telem = asset_telem[:hours]

    # Map pressure records if applicable
    pressure_map = {
        p.get("hour_index"): p.get("pressure_bar")
        for p in pressure_records
        if p.get("asset_tag") == asset_tag
    }

    points = []
    for t in reversed(recent_telem):
        h_idx = t.get("hour_index", 0)
        points.append(
            TelemetryPoint(
                hour_index=h_idx,
                vibration_mm_s=float(t.get("vibration_mm_s", 0.0)),
                temp_c=float(t.get("temp_c", 0.0)),
                current_a=float(t.get("current_a", 0.0)),
                pressure_bar=pressure_map.get(h_idx),
            )
        )

    # Compute quick trend
    trend = "Stable within operating limits"
    if points:
        latest = points[-1]
        v_trip = aclass.get("vibration_trip_mm_s")
        t_trip = aclass.get("temp_trip_c")
        if v_trip and latest.vibration_mm_s >= v_trip:
            trend = f"CRITICAL: Vibration {latest.vibration_mm_s:.2f} mm/s exceeds trip limit {v_trip} mm/s"
        elif t_trip and latest.temp_c >= t_trip:
            trend = f"CRITICAL: Temperature {latest.temp_c:.1f}°C exceeds trip limit {t_trip}°C"
        elif aclass.get("vibration_warning_mm_s") and latest.vibration_mm_s >= aclass.get("vibration_warning_mm_s"):
            trend = f"WARNING: Vibration {latest.vibration_mm_s:.2f} mm/s exceeds warning limit"

    return SensorHistoryResult(
        asset_tag=asset_tag,
        asset_code=asset_code,
        vibration_warning_mm_s=aclass.get("vibration_warning_mm_s"),
        vibration_trip_mm_s=aclass.get("vibration_trip_mm_s"),
        temp_warning_c=aclass.get("temp_warning_c"),
        temp_trip_c=aclass.get("temp_trip_c"),
        pressure_nominal_bar=aclass.get("pressure_nominal_bar"),
        pressure_low_alarm_bar=aclass.get("pressure_low_alarm_bar"),
        points_retrieved=len(points),
        recent_readings=points,
        trend_summary=trend,
    )


def calculate_downtime_cost(asset_tag: Optional[str], downtime_minutes: int) -> DowntimeCostResult:
    """
    Calculate downtime cost based on asset-specific hourly rates (or class default if unknown).

    Args:
        asset_tag: Machine identifier e.g. 'VPW-HYD-PRESS-02' (or None)
        downtime_minutes: Expected or actual downtime duration in minutes
    """
    loader = get_table_loader()
    downtime_minutes = max(0, downtime_minutes)
    hours = downtime_minutes / 60.0

    criticality_data = loader.load_table("asset_criticality")
    matrix_data = loader.load_table("criticality_matrix")

    crit_row = None
    if asset_tag:
        asset_tag = asset_tag.strip().upper()
        crit_row = next((c for c in criticality_data if c.get("asset_tag") == asset_tag), None)

    if crit_row:
        hourly_rate = int(crit_row.get("downtime_cost_per_hour_inr", 18000))
        rate_source = "asset_specific"
        crit_class = crit_row.get("criticality", "B")
        safety_risk = crit_row.get("safety_risk", "MEDIUM")
        env_impact = crit_row.get("environmental_impact", "MAJOR")
    else:
        # Fallback to Class B default rate
        default_row = next((m for m in matrix_data if m.get("criticality") == "B"), {})
        hourly_rate = int(default_row.get("default_downtime_cost_inr_per_hour", 18000))
        rate_source = "class_default"
        crit_class = "B"
        safety_risk = "UNKNOWN"
        env_impact = "UNKNOWN"

    total_cost = int(round(hours * hourly_rate))

    return DowntimeCostResult(
        asset_tag=asset_tag or "UNKNOWN",
        downtime_minutes=downtime_minutes,
        hourly_rate_inr=hourly_rate,
        rate_source=rate_source,
        total_cost_inr=total_cost,
        criticality=crit_class,
        safety_risk=safety_risk,
        environmental_impact=env_impact,
    )


def check_spare_parts_inventory(part_number: str) -> PartInventoryResult:
    """
    Look up spare part stock, unit cost, lead time, and supplier tier.

    Args:
        part_number: Unique part identifier e.g. 'VPW-P-00123'
    """
    loader = get_table_loader()
    part_number = part_number.strip().upper()

    inventory = loader.load_table("inventory")
    item = next((i for i in inventory if i.get("part_number") == part_number), None)
    if not item:
        return PartInventoryResult(
            part_number=part_number,
            error=f"Part '{part_number}' not found in inventory registry",
        )

    part_suppliers = loader.load_table("part_suppliers")
    ps = next((s for s in part_suppliers if s.get("part_number") == part_number), {})

    on_hand = int(item.get("on_hand", 0))
    reorder_point = int(item.get("reorder_point", 0))

    return PartInventoryResult(
        part_number=part_number,
        description=item.get("description", ""),
        asset_code=item.get("asset_code", ""),
        on_hand=on_hand,
        reorder_point=reorder_point,
        unit_cost_inr=int(item.get("unit_cost_inr", 0)),
        lead_time_days=int(item.get("lead_time_days", 0)),
        supplier_tier=item.get("supplier_tier", "T2"),
        supplier_id=ps.get("supplier_id"),
        minimum_order_quantity=ps.get("min_order_quantity"),
        is_stock_low=(on_hand <= reorder_point),
    )


def schedule_technician(
    required_skill: str,
    estimated_hours: int = 4,
    date_str: str = "2026-08-01",
    shift: Optional[str] = None,
) -> TechnicianScheduleResult:
    """
    Query technician calendar for available qualified personnel.

    Args:
        required_skill: Trade required ('Mechanical', 'Electrical', 'Instrumentation', 'Hydraulics', 'Robotics')
        estimated_hours: Job duration in hours
        date_str: Date for work in YYYY-MM-DD format (defaults to 2026-08-01)
        shift: Shift filter 'A', 'B', or 'C' (optional)
    """
    loader = get_table_loader()
    required_skill = required_skill.strip().capitalize()
    estimated_hours = max(1, estimated_hours)

    valid_skills = {"Mechanical", "Electrical", "Instrumentation", "Hydraulics", "Robotics"}
    if required_skill not in valid_skills:
        return TechnicianScheduleResult(
            requested_skill=required_skill,
            estimated_hours=estimated_hours,
            requested_date=date_str,
            error=f"Invalid skill '{required_skill}'. Must be one of {valid_skills}",
        )

    technicians = loader.load_table("technicians")
    calendar = loader.load_table("technician_calendar")

    # Filter technicians by primary or secondary skill
    matching_techs = {
        t["technician_id"]: t for t in technicians
        if t.get("primary_skill") == required_skill or t.get("secondary_skill") == required_skill
    }

    # Query calendar rows
    available_slots = []
    for cal in calendar:
        tech_id = cal.get("technician_id")
        if tech_id not in matching_techs:
            continue
        if cal.get("date") != date_str:
            continue
        if shift and cal.get("shift") != shift:
            continue
        if cal.get("status") != "on_shift":
            continue

        free_hours = int(cal.get("available_hours", 0))
        if free_hours >= estimated_hours:
            t_info = matching_techs[tech_id]
            certs = []
            for cert_key in [
                "hot_work_certified", "confined_space_certified", "work_at_height_certified",
                "high_voltage_certified", "pressure_system_certified"
            ]:
                if t_info.get(cert_key):
                    certs.append(cert_key.replace("_certified", ""))

            available_slots.append(
                TechnicianSlot(
                    technician_id=tech_id,
                    name=t_info.get("name", ""),
                    primary_skill=t_info.get("primary_skill", ""),
                    secondary_skill=t_info.get("secondary_skill"),
                    skill_level=t_info.get("skill_level", "L2"),
                    shift=cal.get("shift", ""),
                    date=date_str,
                    available_hours=free_hours,
                    loto_authorised=bool(t_info.get("loto_authorised", False)),
                    certifications=certs,
                )
            )

    # Sort: Senior technicians (L3) with highest available hours first
    level_rank = {"L3": 3, "L2": 2, "L1": 1}
    available_slots.sort(key=lambda s: (level_rank.get(s.skill_level, 0), s.available_hours), reverse=True)

    recommendation = None
    if available_slots:
        top = available_slots[0]
        recommendation = f"Assign {top.name} ({top.technician_id}, {top.skill_level}) on shift {top.shift} ({top.available_hours}h available)"

    return TechnicianScheduleResult(
        requested_skill=required_skill,
        estimated_hours=estimated_hours,
        requested_date=date_str,
        requested_shift=shift,
        available_technicians=available_slots,
        count=len(available_slots),
        recommendation=recommendation,
    )
