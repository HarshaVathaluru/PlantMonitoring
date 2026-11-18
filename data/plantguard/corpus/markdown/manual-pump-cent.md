# Centrifugal Process Pump (PUMP-CENT) Equipment Manual and SOP

**VINDHYA PRECISION WORKS: MAINTENANCE SOP-PUMP-CENT-01**

**1.0 PURPOSE AND SCOPE**
1.1 This document defines the operating envelope and maintenance requirements for Asset Class PUMP-CENT (Centrifugal Process Pump).
1.2 Compliance with these thresholds is mandatory for all personnel under the direction of the Maintenance Engineering Lead, Marcus Vane.

**2.0 OPERATING PARAMETERS AND ALARMS**
2.1 Normal operating range is defined as 1.2–4.0 mm/s RMS vibration and 38–66°C surface temperature.
2.2 Alarm and Trip setpoints are hard-coded into the CMS-2000 monitoring system as follows:
   2.2.1 Vibration: Warning at 5.0 mm/s RMS; Trip at 8.0 mm/s RMS.
   2.2.2 Temperature: Warning at 75°C; Trip at 90°C.
   2.2.3 Pressure: Nominal 4.2 bar; Low-pressure alarm at 3.4 bar.

**3.0 PREVENTIVE MAINTENANCE SCHEDULE**
3.1 The base preventive maintenance interval is 4,000 running hours.
3.2 Lead responsibility is assigned to Mechanical Trade; Instrumentation Trade must provide support for calibration verification.
3.3 Required Parts List:
   3.3.1 VPW-P-00007 (Rate filter)
   3.3.2 VPW-P-00011 (Nation sensor)
   3.3.3 VPW-P-00020 (Once bearing)
   3.3.4 VPW-P-00023 (Discussion filter)
   3.3.5 VPW-P-00026 (Second seal)
   3.3.6 VPW-P-00030 (Author seal)
   3.3.7 VPW-P-00031 (Western bearing)
   3.3.8 VPW-P-00033 (Trade valve)

**4.0 FAULT CODES AND CORRECTIVE ACTIONS**
4.1 Fault F-01 (Cavitation): Caused by inlet obstruction; check and replace VPW-P-00033 (Trade valve) or clear suction pipe.
4.2 Fault F-02 (Over-temp): Caused by bearing degradation; replace VPW-P-00020 (Once bearing) and VPW-P-00031 (Western bearing).
4.3 Fault F-03 (Seal Leak): Caused by face wear; replace VPW-P-00026 (Second seal) and VPW-P-00030 (Author seal).
4.4 Fault F-04 (Flow Err): Caused by filtration saturation; replace VPW-P-00007 (Rate filter) and VPW-P-00023 (Discussion filter).
4.5 Fault F-05 (Sensor Drift): Caused by calibration loss; replace VPW-P-00011 (Nation sensor).
4.6 Fault F-06 (Vibration Spike): Caused by coupling misalignment; perform laser alignment and re-torque mounting bolts.

**5.0 TECHNICAL SPECIFICATIONS AND SAFETY**
5.1 Torque Specifications:
   5.1.1 Housing bolts: 85 Nm.
   5.1.2 Flange bolts: 110 Nm.
   5.1.3 Impeller nut: 45 Nm.
5.2 Hazardous Energy Control:
   5.2.1 All maintenance requires isolation of Electrical (480V) and Hydraulic (Process line pressure) sources.
   5.2.2 Actions requiring mandatory Lockout/Tagout (LOTO) and a formal Permit to Work include: Bearing replacement, seal replacement, and impeller housing disassembly.
   5.2.3 Exception: Sensor replacement (VPW-P-00011) may be performed with LOTO only, provided the pump is at zero-speed and the process suction valve is locked shut.

**6.0 AUTHORIZATION**
6.1 Document Owner: Marcus Vane, Maintenance Engineering Lead.
6.2 Last Revision: 14 October 2023.
