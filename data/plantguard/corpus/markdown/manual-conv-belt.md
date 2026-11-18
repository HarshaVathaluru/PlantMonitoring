# Main Line Belt Conveyor (CONV-BELT) Equipment Manual and SOP

**VINDHYA PRECISION WORKS: MAINTENANCE ENGINEERING DIVISION**
**ASSET CLASS: CONV-BELT (MAIN LINE BELT CONVEYOR)**
**DOCUMENT REF: SOP-CONV-BELT-09**

### 1. OPERATIONAL SPECIFICATIONS AND ALARM LIMITS
1.1. The Main Line Belt Conveyor shall operate within the following nominal parameters:
   * 1.1.1. Vibration (RMS): 1.2 mm/s to 4.0 mm/s.
   * 1.1.2. Surface Temperature: 38°C to 66°C.
   * 1.1.3. Process Pressure: Not applicable to this asset class (N/A).
   * 1.1.4. Current: 14.5 A to 18.2 A (rated load).

1.2. Condition-monitoring system setpoints for automated alerts and system trips are defined as:
   * 1.2.1. Vibration Warning: 7.1 mm/s RMS.
   * 1.2.2. Vibration Trip: 11.0 mm/s RMS.
   * 1.2.3. Surface Temperature Warning: 70°C.
   * 1.2.4. Surface Temperature Trip: 84°C.

### 2. PREVENTIVE MAINTENANCE (PM) SCHEDULE
2.1. The base PM interval is 1,000 running hours.
2.2. Responsibility: Mechanical (Primary), Electrical (Support).
2.3. Tasks required at 1,000-hour intervals:
   * 2.3.1. Inspection of belt tension and tracking.
   * 2.3.2. Lubrication of drive bearings.
   * 2.3.3. Verification of "Artist sensor" calibration.
   * 2.3.4. Inspection of "Avoid seal" and "Drop seal" integrity.

### 3. FAULT CODE TABLE
| Condition | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| FC-01: Belt Slip | Low belt tension | Adjust tensioner to 150 Nm torque. |
| FC-02: High Temp | Bearing failure | Replace bearing and "Own seal". |
| FC-03: Sensor Fail | "Artist sensor" fault | Replace sensor; test signal loop. |
| FC-04: Contactor Err | Stuck "Attack contactor" | Replace contactor; check coil voltage. |
| FC-05: Phase Loss | Blown "Mention contactor" | Inspect cabling; replace contactor. |
| FC-06: Belt Tracking | Damaged "Avoid belt" | Replace belt section; realign rollers. |

### 4. SPARE PARTS AND CONSUMABLES
Use only the following part numbers from the VPW inventory system:
* VPW-P-00016: Attack contactor
* VPW-P-00025: Avoid seal
* VPW-P-00028: Artist sensor
* VPW-P-00029: Drop seal
* VPW-P-00035: Avoid belt
* VPW-P-00040: Mention contactor
* VPW-P-00044: Several sensor
* VPW-P-00047: Own seal

### 5. TORQUE SPECIFICATIONS
5.1. Drive Pulley Mounting Bolts: 210 Nm.
5.2. Belt Tensioner Adjustment Nut: 150 Nm.
5.3. Electrical Terminal Connections (M8): 12 Nm.

### 6. SAFETY, LOCKOUT, AND PERMIT REQUIREMENTS
6.1. Hazardous energy sources: Electrical (480V supply), Mechanical (Kinetic belt energy/Tensioned springs).
6.2. The following corrective actions are designated as Safety-Critical and require a mandatory Lockout/Tagout (LOTO) procedure and an approved Permit to Work (PTW) signed by the Shift Supervisor:
   * 6.2.1. Replacement of "Avoid belt" (FC-06).
   * 6.2.2. Replacement of "Attack contactor" (FC-04) or "Mention contactor" (FC-05).
   * 6.2.3. Any maintenance involving the removal of the drive motor housing.
   * 6.2.4. Manual tensioning adjustments exceeding 10mm of travel.

**Authorized by:** 
*R. K. Varma, Maintenance Engineering Lead*
