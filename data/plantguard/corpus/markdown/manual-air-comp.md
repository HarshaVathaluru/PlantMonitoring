# Rotary Screw Air Compressor (AIR-COMP) Equipment Manual and SOP

**VINDHYA PRECISION WORKS: MAINTENANCE SOP-AIR-COMP-01**
**DOCUMENT ID:** VPW-MAN-AIR-772
**SUBJECT:** Operation and Maintenance of Rotary Screw Air Compressor (AIR-COMP)
**APPROVED BY:** Rajesh Varma, Lead Maintenance Engineer
**EFFECTIVE DATE:** 2023-10-14

---

### 1. OPERATING PARAMETERS AND THRESHOLDS
1.1. **Normal Operational Range:** Asset AIR-COMP shall maintain vibration levels of 1.2–4.0 mm/s RMS and surface temperature of 38–66 °C during standard production cycles.
1.2. **Instrumentation Limits:**
   * 1.2.1. **Vibration:** Warning setpoint at 6.3 mm/s RMS; Trip setpoint at 9.5 mm/s RMS.
   * 1.2.2. **Temperature:** Warning setpoint at 88 °C; Trip setpoint at 102 °C.
   * 1.2.3. **Pressure:** Nominal operating pressure of 7.5 bar; Low-pressure alarm at 6.2 bar.
   * 1.2.4. **Current:** Nominal full-load current (FLC) 42A; Overload trip set at 48A.

### 2. PREVENTIVE MAINTENANCE (PM) SCHEDULE
2.1. Base PM Interval: Every 2,000 running hours (±50 hours tolerance).
2.2. **Responsibility:** Mechanical trade is lead; Instrumentation trade shall provide support for sensor calibration and signal verification.

| Interval (Hours) | Task Description |
| :--- | :--- |
| 2,000 | Replace VPW-P-00036 (My belt); Inspect VPW-P-00001 (Road seal). |
| 4,000 | Replace VPW-P-00034 (Give valve); Inspect VPW-P-00003 (Sell bearing). |
| 8,000 | Full sensor calibration; Replace VPW-P-00106 (Time sensor). |

### 3. FAULT CODE TABLE
3.1. **FAULT-01 (Low Flow):** Caused by intake obstruction. Corrective action: Inspect and clean intake filter.
3.2. **FAULT-02 (Over-Temp):** Caused by failed cooling fan. Corrective action: Check VPW-P-00019 (Per contactor) for contact pitting.
3.3. **FAULT-03 (High Vibration):** Caused by misalignment. Corrective action: Re-tension VPW-P-00036 (My belt) to 450N.
3.4. **FAULT-04 (Pressure Drop):** Caused by leakage. Corrective action: Inspect seals and replace VPW-P-00001 (Road seal) if compromised.
3.5. **FAULT-05 (Sensor Fault):** Caused by drift. Corrective action: Test and replace VPW-P-00106 (Time sensor).
3.6. **FAULT-06 (Control Failure):** Caused by logic relay failure. Corrective action: Replace VPW-P-00050 (Eight contactor) or VPW-P-00075 (Such contactor).

### 4. SPARE PARTS AND CONSUMABLES
4.1. Only parts listed in the VPW Inventory System shall be installed.
*   **VPW-P-00001:** Road seal
*   **VPW-P-00003:** Sell bearing
*   **VPW-P-00019:** Per contactor
*   **VPW-P-00034:** Give valve
*   **VPW-P-00036:** My belt
*   **VPW-P-00050:** Eight contactor
*   **VPW-P-00075:** Such contactor
*   **VPW-P-00106:** Time sensor

### 5. TORQUE SPECIFICATIONS
5.1. Main drive pulley bolts: 85 Nm.
5.2. Discharge flange bolts: 55 Nm (apply cross-pattern tightening).
5.3. Bearing housing caps: 28 Nm.

### 6. SAFETY-CRITICAL ACTIONS AND LOCKOUT
6.1. **Hazardous Energy:** All maintenance involving internal mechanical assemblies or electrical cabinets requires isolation of **Electrical** (LOTO required) and **Pneumatic** (bleed-down required) energy sources.
6.2. **Permit Requirements:** The following tasks are classified as safety-critical and require an approved Work Permit:
   * 6.2.1. Any replacement of VPW-P-00034 (Give valve).
   * 6.2.2. Any adjustment or replacement of VPW-P-00036 (My belt).
   * 6.2.3. Any work performed inside the primary electrical enclosure involving VPW-P-00050 or VPW-P-00075.
6.3. Failure to secure a Lockout-Tagout (LOTO) permit prior to these actions will result in immediate disciplinary review by the Plant Safety Manager.
