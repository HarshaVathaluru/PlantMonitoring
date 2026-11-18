# Six-Axis Welding Robot (ROBOT-WELD) Equipment Manual and SOP

**VINDHYA PRECISION WORKS: EQUIPMENT MANUAL AND SOP**
**ASSET CLASS: ROBOT-WELD (SIX-AXIS WELDING ROBOT)**
**DOCUMENT ID: VPW-OPS-WELD-04**

### 1.0 OPERATING PARAMETERS AND ALARM THRESHOLDS
1.1. Healthy operation for asset ROBOT-WELD is defined as:
   1.1.1. Vibration: 1.2 mm/s to 4.0 mm/s RMS.
   1.1.2. Surface Temperature: 38°C to 66°C.
1.2. Condition-monitoring system triggers are set as follows:
   1.2.1. Vibration Warning: 4.6 mm/s RMS.
   1.2.2. Vibration Trip: 7.3 mm/s RMS (Automatic E-Stop).
   1.2.3. Surface Temperature Warning: 74°C.
   1.2.4. Surface Temperature Trip: 88°C (Automatic E-Stop).
1.3. Process Pressure: Asset class ROBOT-WELD does not utilize monitored process pressure sensors. Any pressure gauges observed on integrated auxiliary equipment are for site-utility reference only and are not monitored by the central SCADA system.

### 2.0 MAINTENANCE RESPONSIBILITY AND FREQUENCY
2.1. Lead Responsibility: Robotics Department.
2.2. Support Responsibility: Electrical Department.
2.3. Preventive Maintenance (PM) Interval: 1250 running hours, as recorded by the Internal Asset Clock.
2.4. Hazardous Energy Sources: Electrical (480V, 3-Phase) and Pneumatic (85 PSI supply). Both must be locked out per VPW-LOTO-01 prior to any maintenance.

### 3.0 PREVENTIVE MAINTENANCE SCHEDULE (BY RUNNING HOURS)
3.1. 1250 Hours: Inspect VPW-P-00060 (Health filter); replace if visual loading is >30%. Inspect VPW-P-00017 (Ground belt) for fraying.
3.2. 2500 Hours: Replace VPW-P-00060 (Health filter) and VPW-P-00074 (Group sensor). 
3.3. 5000 Hours: Full drive-train inspection. Torque check on VPW-P-00000 (Show coupling) to 45 Nm and VPW-P-00059 (Lawyer coupling) to 52 Nm. Replace VPW-P-00018 (Against coupling) and VPW-P-00078 (Energy belt).

### 4.0 FAULT CODES AND TROUBLESHOOTING
4.1. Error 101 (Linkage Drift): Caused by worn VPW-P-00000 (Show coupling). Corrective action: Inspect coupling for radial play and replace.
4.2. Error 104 (Ground Fault): Caused by degraded VPW-P-00017 (Ground belt). Corrective action: Inspect continuity and replace belt.
4.3. Error 209 (Filter Saturation): Caused by clogged VPW-P-00060 (Health filter). Corrective action: Replace filter.
4.4. Error 312 (Signal Noise): Caused by failing VPW-P-00074 (Group sensor). Corrective action: Replace sensor and recalibrate axis home position.
4.5. Error 405 (Power Relay Fail): Caused by stuck contacts in VPW-P-00089 (Two contactor). Corrective action: Replace contactor.
4.6. Error 502 (Drive Tension): Caused by stretched VPW-P-00078 (Energy belt). Corrective action: Adjust tension or replace belt.

### 5.0 CONSUMABLES AND SPARE PARTS LIST
The following parts are authorized for ROBOT-WELD:
*   VPW-P-00000: Show coupling
*   VPW-P-00017: Ground belt
*   VPW-P-00018: Against coupling
*   VPW-P-00059: Lawyer coupling
*   VPW-P-00060: Health filter
*   VPW-P-00074: Group sensor
*   VPW-P-00078: Energy belt
*   VPW-P-00089: Two contactor

### 6.0 SAFETY-CRITICAL CORRECTIVE ACTIONS
6.1. The following tasks are designated safety-critical and require a formal Lockout/Tagout (LOTO) procedure and a Confined Space or High-Voltage Permit signed by Maintenance Manager Ravi Varma:
   6.1.1. Replacement of VPW-P-00089 (Two contactor).
   6.1.2. Any mechanical disassembly involving VPW-P-00000 (Show coupling) or VPW-P-00059 (Lawyer coupling).
   6.1.3. Any repair involving the electrical isolation of the primary supply to the robotic arm.
