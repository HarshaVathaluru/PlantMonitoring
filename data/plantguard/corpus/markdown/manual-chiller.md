# Water-Cooled Process Chiller (CHILLER) Equipment Manual and SOP

**DOCUMENT ID: VPW-OPS-CHILL-04**
**ASSET CLASS: CHILLER**
**REVISION: 2.1**
**ISSUING AUTHORITY: Maintenance Engineering Lead**

### 1.0 OPERATIONAL SPECIFICATIONS
1.1 All CHILLER units shall be monitored via the Integrated Condition-Monitoring System (ICMS).
1.2 Nominal Operating Pressure: 3.0 bar. Low-pressure alarm setpoint: 2.4 bar.
1.3 Vibration Limits: 
    1.3.1 Healthy Range: 1.2–4.0 mm/s RMS.
    1.3.2 Warning Threshold: 5.3 mm/s RMS.
    1.3.3 Trip Threshold: 8.2 mm/s RMS.
1.4 Surface Temperature Limits:
    1.4.1 Healthy Range: 38–66°C.
    1.4.2 Warning Threshold: 80°C.
    1.4.3 Trip Threshold: 95°C.
1.5 Current: Nominal operational draw is 42A at 415V/3ph. Exceeding 55A for >10 seconds triggers a breaker trip.

### 2.0 PREVENTIVE MAINTENANCE (PM) SCHEDULE
2.1 Base Interval: 3000 running hours.
2.2 Responsible Trade: Mechanical (Primary), Electrical (Support).
2.3 PM Tasks:
    2.3.1 3000 Hours: Replace VPW-P-00022 (Per filter). Inspect VPW-P-00041 (Difficult seal).
    2.3.2 6000 Hours: Replace VPW-P-00041 (Difficult seal) and VPW-P-00043 (Cause valve).
    2.3.3 9000 Hours: Full teardown inspection of VPW-P-00010 (We bearing) and VPW-P-00015 (Down coupling).

### 3.0 FAULT CODES AND CORRECTIVE ACTIONS
3.1 **Code F-01 (Low Pressure):** Caused by refrigerant leak. Corrective Action: Inspect lines, repair leak, recharge system.
3.2 **Code F-02 (High Vibration):** Caused by coupling misalignment. Corrective Action: Realign VPW-P-00015 (Down coupling) and torque to 45Nm.
3.3 **Code F-03 (Thermal Trip):** Caused by clogged filter. Corrective Action: Replace VPW-P-00022 (Per filter).
3.4 **Code F-04 (Sensor Drift):** Caused by faulty input. Corrective Action: Replace VPW-P-00014 (End sensor).
3.5 **Code F-05 (Valve Failure):** Caused by solenoid fatigue. Corrective Action: Replace VPW-P-00012 (Live valve).
3.6 **Code F-06 (Logic Error):** Caused by calibration loss. Corrective Action: Reset/Replace VPW-P-00027 (Program sensor).

### 4.0 SPARE PARTS INVENTORY
Technicians must draw only the following parts for CHILLER repairs:
*   VPW-P-00010: We bearing
*   VPW-P-00012: Live valve
*   VPW-P-00014: End sensor
*   VPW-P-00015: Down coupling
*   VPW-P-00022: Per filter
*   VPW-P-00027: Program sensor
*   VPW-P-00041: Difficult seal
*   VPW-P-00043: Cause valve

### 5.0 SAFETY AND ISOLATION
5.1 Hazardous Energy Sources: Electrical (High Voltage) and Refrigerant Pressure (High Pressure).
5.2 Safety-Critical Actions: The following tasks require mandatory Lockout-Tagout (LOTO) and a signed Permit-to-Work (PTW):
    5.2.1 Any intervention involving the refrigerant circuit (e.g., replacing VPW-P-00043).
    5.2.2 Any replacement of electrical components (e.g., VPW-P-00027).
    5.2.3 Any physical disassembly of the drivetrain (e.g., VPW-P-00010).
5.3 LOTO Procedure: Ensure main disconnect is locked in the OFF position and refrigerant line pressure is bled to 0.0 bar before loosening any seals or valve bodies.

### 6.0 TORQUE SPECIFICATIONS
6.1 Fasteners securing the compressor housing must be torqued to 85Nm.
6.2 Connection flanges for VPW-P-00043 (Cause valve) must be torqued to 22Nm.
6.3 All electrical terminations must be torqued to 3.5Nm.
