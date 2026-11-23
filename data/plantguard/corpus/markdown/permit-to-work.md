# Permit to Work and Safety-Critical Task Standard

# ENGINEERING STANDARD: VPW-ES-402
**TITLE:** Permit-to-Work (PTW) Standard  
**EFFECTIVE DATE:** 14 January 2025  
**CUSTODIAN:** Plant Maintenance Engineering Lead  
**APPLIES TO:** All Vindhya Precision Works (VPW) Manufacturing Plants and Associated Facilities  

---

## 1. PURPOSE AND SCOPE

**1.1** This document defines the mandatory Permit-to-Work (PTW) protocol for all non-routine, hazardous, and high-energy maintenance, construction, and modification activities conducted within Vindhya Precision Works (VPW) facilities by internal personnel or contracted third parties.

**1.2** Compliance with this standard is a strict condition of employment and contract execution. Any deviation without written authorization from the Plant Operations Manager constitutes a critical safety violation.

---

## 2. TASK CLASSES REQUIRING A PERMIT

No person shall commence work within the following five designated task classes without an active, physically posted Class-specific PTW issued in accordance with Section 4.

### 2.1 Hot Work (HW)
Any work involving open flames, electric arc welding, cutting, grinding, soldering, brazing, or the generation of a localized ignition source capable of igniting flammable gases, vapors, or combustible particulate.

### 2.2 Confined Space Entry (CS)
Entry into any enclosure that:
*   Has limited or restricted means for entry or exit;
*   Is large enough for a worker to bodily enter and perform assigned work; and
*   Is not designed for continuous employee occupancy.  
*Note:* This includes tanks, pits exceeding 1.2 meters in depth, degreasing vats, and large-diameter ductwork.

### 2.3 Work at Height (WAH)
Any work conducted at an elevation where a fall could result in personal injury, specifically any activity where a worker operates 1.8 meters or more above ground level, or where work is performed over machinery, open process vats, or unbarricaded floor openings regardless of depth.

### 2.4 High-Voltage Electrical (HVE)
Any work performed on or near energized or de-energized electrical infrastructure operating at or above 1,000 Volts Alternating Current (VAC) or 1,500 Volts Direct Current (VDC).

### 2.5 Pressure System Line Breaking (PSLB)
The mechanical breaching, opening, flange separation, or dismantling of any piping system, vessel, heat exchanger, or hydraulic accumulator containing, or previously containing, hazardous, toxic, flammable, or pressurized fluids (pneumatic or hydraulic exceeding 6.9 bar / 100 psi).

---

## 3. PERMIT VALIDITY PERIOD

**3.1** Standard PTW documents are valid for a maximum duration of twelve (12) consecutive hours from the exact timestamp of issuance, or until the end of the current operational shift, whichever expires first.

**3.2** Permits may be revalidated for one (1) subsequent twelve-hour shift by the original Issuing Authority, provided:
*   The job site has been physically reinspected;
*   No scope changes have occurred; and
*   All isolation, gas-testing, and personal protective equipment (PPE) verifications are re-signed.

**3.3** Under no circumstances shall any single PTW remain active for a cumulative duration exceeding twenty-four (24) hours.

---

## 4. NAMED ROLES: ISSUANCE AND ACCEPTANCE

Execution of a PTW requires formal authorization and sign-off by designated individuals holding active internal certification credentials issued by the VPW Safety Engineering Department.

### 4.1 Permit Issuing Authority (PIA)
The following named individuals, or their formally designated operational deputies listed in Appendix A of this standard, are authorized to issue PTWs:
*   **Arjun Mehta** (Plant Maintenance Engineering Lead)
*   **Sunita Rao** (Lead Facility Safety Officer)
*   **Vikram Patel** (Utilities and Infrastructure Superintendent)

### 4.2 Permit Accepting Authority (PAA)
The PAA is the competent person in direct charge of the execution crew who receives the permit, conducts the toolbox talk, and ensures adherence to safety controls. Authorized PAAs are restricted to:
*   Certified Lead Technicians
*   Contractor Site Supervisors holding valid VPW Safety Inductions
*   Senior Shift Foremen

---

## 5. GAS-TESTING REQUIREMENTS AND RE-TEST INTERVALS

**5.1** Atmospheric testing using a calibrated, multi-gas meter (detecting Oxygen, Lower Explosive Limit [LEL], Carbon Monoxide, and Hydrogen Sulfide) is mandatory prior to the issuance of any Hot Work or Confined Space permit, and prior to breaking any pressure system previously containing asphyxiant or toxic media.

### 5.2 Mandatory Acceptance Thresholds
Work shall not commence, and permits shall not be issued, unless baseline atmospheric readings meet the following exact criteria:
*   **Oxygen ($O_2$):** Exactly 20.9% by volume (Acceptable operating window: 19.5% to 23.5%).
*   **Lower Explosive Limit (LEL):** Less than 1.0% LEL.
*   **Carbon Monoxide (CO):** Less than 25 parts per million (ppm).
*   **Hydrogen Sulfide ($H_2S$):** 0.0 ppm.

### 5.3 Mandatory Re-Test Intervals
*   **Confined Space Entry:** Atmospheric re-testing must be executed and logged on the permit sheet at intervals not exceeding two (2) hours.
*   **Hot Work:** Continuous atmospheric monitoring is mandatory if flammable materials are stored within fifteen (15) meters. Where continuous monitoring is not technically feasible, periodic re-testing must occur at intervals not exceeding four (4) hours.
*   **Immediate Re-Test Triggers:** Work must immediately cease, and a full re-test must be executed, following any operational process upset, ventilation fan failure, unpredicted odor detection, or work stoppage exceeding thirty (30) minutes.

---

## 6. CONDITIONS THAT AUTOMATICALLY VOID A PERMIT

An active PTW becomes null and void immediately upon the occurrence of any of the following events, requiring complete re-evaluation, new isolation verification, and re-issuance before work can resume:

**6.1** Sounding of the plant emergency evacuation siren or activation of the site fire alarm system.

**6.2** Unplanned loss of primary process isolation integrity, including valve leakage, rupture of temporary blanks, or failure of electrical lockout/tagout (LOTO) devices.

**6.3** Any deviation from the defined job scope, methodology, or equipment specified on the face of the permit document.

**6.4** Failure of atmospheric gas-testing parameters to remain within the thresholds defined in Section 5.2 during a scheduled or random re-test.

**6.5** Absence of the designated Permit Accepting Authority (PAA) or the active work crew from the immediate job site for a continuous period exceeding sixty (60) minutes without formal suspension logging.

**6.6** Occurrence of a structural, mechanical, or electrical incident, near-miss, or injury within the immediate worksite zone.

---

## 7. AUTOMATED ADVISORY SYSTEM RESTRICTIONS

**7.1** The VPW Digital Maintenance Management System (DMMS) includes an automated advisory engine designed to assist in risk evaluation and permit preparation. 

**7.2** The automated advisory system must **never** issue, validate, sign off, or close a Permit-to-Work without explicit human authorization entered via physical biometric verification or secure password confirmation by a certified Permit Issuing Authority (PIA).

**7.3** Specifically, the automated advisory system is strictly prohibited from autonomously issuing recommendations or clearances in the following categories:
1.  **Isolation Validation:** Determining that a machine, circuit, or piping run is fully de-energized, bled, zero-energy verified, and safe to break.
2.  **Confined Space Clearance:** Declaring an internal vessel atmosphere safe for human entry without mandatory physical counter-signature of fresh calibration logs by the Lead Facility Safety Officer.
3.  **Simultaneous Operations (SIMOPS) Override:** Permitting conflicting high-risk activities (e.g., executing Hot Work directly beneath an active Work at Height zone or inside an active chemical boundary) to proceed concurrently.
4.  **PPE Downgrade:** Recommending any reduction in mandated respiratory, fall-arrest, or chemical-resistance protection below baseline engineering standards for a specific hazard class.
5.  **Permit Extension:** Granting the twelve-hour shift extension outlined in Section 3.2 without an independent physical site audit conducted and logged by a human PIA.

---
**REVISION HISTORY:**  
*   Rev 01 (14-Jan-2025): Initial release replacing legacy manual safety forms.
