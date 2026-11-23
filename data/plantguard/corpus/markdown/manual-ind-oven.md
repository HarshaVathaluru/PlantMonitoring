# Continuous Curing Oven (IND-OVEN) Equipment Manual and SOP

**VINDHYA PRECISION WORKS: EQUIPMENT MANUAL & SOP**
**ASSET CLASS: IND-OVEN (CONTINUOUS CURING OVEN)**
**Document ID: VPW-OPS-IND-OVEN-001**
**Revision: 4.2**

---

### 1. OPERATING PARAMETERS AND ALARM SETPOINTS
1.1. The IND-OVEN asset class shall operate within the following steady-state design ranges:
1.1.1. Vibration: 1.2 mm/s to 4.0 mm/s RMS.
1.1.2. Surface Temperature: 38°C to 66°C.
1.2. Condition-monitoring system triggers for automated shutdown or intervention are defined as:
1.2.1. Vibration Warning: 4.8 mm/s RMS; Trip: 7.5 mm/s RMS.
1.2.2. Surface Temperature Warning: 90°C; Trip: 105°C.
1.3. Process Pressure: This asset class does not utilize monitored process pressure; no pressure limits apply to this equipment.
1.4. Current: Nominal draw is 42A per phase. Overcurrent trip is set at 52A.

### 2. PREVENTIVE MAINTENANCE (PM) SCHEDULE
2.1. The base preventive maintenance interval for IND-OVEN is 1,500 running hours.
2.2. Responsibility: Primary execution by Electrical Trade; Instrumentation Trade to provide support for sensor calibration and signal verification.
2.3. Schedule:
2.3.1. 1,500 Hours: Inspection of "Family belt" and "Relationship belt"; lubrication of "Should bearing".
2.3.2. 3,000 Hours: Full replacement of "Part contactor" and "Material contactor".
2.3.3. 4,500 Hours: Inspection of "Forget valve" and "Race valve"; replacement of "Reason seal".

### 3. FAULT CODE TABLE
| Fault Code | Description | Probable Cause | Corrective Action |
| :--- | :--- | :--- | :--- |
| E-101 | Belt Slip | Degraded "Family belt" tension | Adjust tensioner to 15 Nm |
| E-102 | Bearing Overheat | Failed "Should bearing" lubrication | Replace bearing |
| E-201 | Contact Failure | Pitted "Part contactor" | Replace contactor |
| E-202 | Current Surge | Short in "Material contactor" | Replace contactor |
| E-301 | Pressure Leak | Worn "Reason seal" | Replace seal |
| E-401 | Valve Stasis | Debris in "Forget valve" | Inspect and clean or replace valve |

### 4. SPARE PARTS LIST
4.1. Only the following approved components are to be utilized for maintenance:
*   VPW-P-00004: Forget valve
*   VPW-P-00038: Family belt
*   VPW-P-00039: Relationship belt
*   VPW-P-00048: Part contactor
*   VPW-P-00052: Material contactor
*   VPW-P-00058: Reason seal
*   VPW-P-00069: Race valve
*   VPW-P-00073: Should bearing

### 5. TORQUE SPECIFICATIONS
5.1. All M10 terminal lugs on the "Part contactor" and "Material contactor" must be torqued to 18 Nm.
5.2. "Should bearing" housing bolts must be torqued to 35 Nm in a cross-pattern.

### 6. SAFETY-CRITICAL ACTIONS AND LOCKOUT
6.1. The following actions are deemed safety-critical, requiring full Lockout/Tagout (LOTO) of electrical and thermal energy sources and an approved permit:
6.1.1. Replacement of "Part contactor" or "Material contactor" (Electrical isolation).
6.1.2. Disassembly of "Race valve" or "Forget valve" (Thermal/Pressure isolation).
6.1.3. Replacement of "Should bearing" (Mechanical/Electrical isolation).
6.2. Maintenance personnel must verify zero energy state via an intrinsically safe multimeter before initiating any corrective action listed in 6.1.
