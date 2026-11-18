# Vertical CNC Machining Centre (CNC-MILL) Equipment Manual and SOP

**DOCUMENT ID: VPW-OPS-CNC-MILL-04**
**ASSET CLASS: CNC-MILL (Vertical Machining Centre)**
**EFFECTIVE DATE: 2023-10-12**
**MAINTENANCE LEAD: Arthur P. Sterling**

### 1.0 OPERATIONAL SPECIFICATIONS AND MONITORING
1.1 All CNC-MILL units must be operated within the following parameters. Deviations require immediate investigation by the Mechanical lead.
1.2 **Vibration Limits:** Normal operating range is 1.2–4.0 mm/s RMS.
    *   Warning Alarm: 4.5 mm/s RMS.
    *   Trip/Shutdown Threshold: 7.1 mm/s RMS.
1.3 **Surface Temperature Limits:** Normal operating range is 38–66 °C.
    *   Warning Alarm: 72 °C.
    *   Trip/Shutdown Threshold: 86 °C.
1.4 **Process Pressure:** This asset class does not utilize a monitored process pressure system. All sensors reporting pressure for this asset are to be ignored.
1.5 **Current Limits:** The spindle motor operating current is rated at 42A ± 2A. Any sustained reading >50A for >15 seconds shall trigger an emergency stop.

### 2.0 PREVENTIVE MAINTENANCE (PM) SCHEDULE
2.1 The base PM interval for all CNC-MILL assets is 500 running hours.
2.2 Maintenance responsibility is assigned to the Mechanical Trade, with Electrical support as required for sensor calibration and power isolation.
2.3 **PM Tasks:**
    *   **500h:** Replace VPW-P-00008 (Hour filter) and VPW-P-00076 (Training filter). Inspect VPW-P-00054 (Investment bearing) for play.
    *   **1000h:** Replace VPW-P-00006 (Remain seal). Recalibrate VPW-P-00051 (Still sensor) and VPW-P-00079 (Dark sensor).
    *   **2000h:** Full inspection and replacement of VPW-P-00067 (Report coupling) and VPW-P-00021 (Drug valve).

### 3.0 FAULT CODES AND TROUBLESHOOTING
3.1 **E-01 (Spindle Stall):** Caused by excessive tool load or seized VPW-P-00054. Action: Clear chips, inspect bearing, reset controller.
3.2 **E-02 (Thermal Excursion):** Caused by coolant failure or blocked VPW-P-00008. Action: Clean filter, verify pump flow.
3.3 **E-03 (Sensor Drift):** Caused by contaminated VPW-P-00051. Action: Clean sensor lens with industrial solvent.
3.4 **E-04 (Comm-Loss):** Caused by loose VPW-P-00067. Action: Re-torque coupling to 18 Nm.
3.5 **E-05 (Valve Stiction):** Caused by sediment in VPW-P-00021. Action: Disassemble and flush valve body.
3.6 **E-06 (Air-Purge Fault):** Caused by saturated VPW-P-00076. Action: Replace filter element immediately.

### 4.0 SPARE PARTS INVENTORY
4.1 The following parts are exclusively authorized for CNC-MILL maintenance:
    *   VPW-P-00006: Remain seal
    *   VPW-P-00008: Hour filter
    *   VPW-P-00021: Drug valve
    *   VPW-P-00051: Still sensor
    *   VPW-P-00054: Investment bearing
    *   VPW-P-00067: Report coupling
    *   VPW-P-00076: Training filter
    *   VPW-P-00079: Dark sensor

### 5.0 SAFETY AND LOCKOUT PROCEDURES
5.1 All CNC-MILL units possess two hazardous energy sources: Electrical (480V 3-phase) and Pneumatic (6 bar compressed air).
5.2 The following corrective actions are designated **Safety-Critical** and require a validated Lockout/Tagout (LOTO) permit prior to work:
    *   Replacement of VPW-P-00054 (Investment bearing).
    *   Replacement of VPW-P-00067 (Report coupling).
    *   Replacement of VPW-P-00021 (Drug valve).
5.3 Any maintenance task involving the opening of the spindle head cabinet requires a dual-lockout of the main disconnect and the pneumatic isolation valve.
