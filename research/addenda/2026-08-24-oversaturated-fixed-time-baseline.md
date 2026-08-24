# CADENCE — Oversaturated Fixed-Time Signal Timing (Addendum, 2026-08-24)

## 1. Question

**Open question.** Is Webster-style cycle and split tuning, including its Highway Capacity Manual (HCM) descendants, valid at degree of saturation greater than or equal to 1; if not, what fixed-time practice is defensible for CADENCE's oversaturated M3 evaluation?

## 2. Why This Matters to CADENCE

**Inference.** M3 calls the fixed-time controller a tuned classical baseline, while `TC-D01`, `TC-D03`, and `CM-D06` require evaluation above capacity with physical spillback and queue management. The conclusion bears directly on whether a later controller is compared with a competent reference or with a method applied beyond its domain.

**Inference.** The evidence bears on `TC-D04` and narrows `TC-D01`, `TC-D03`, and `CM-D06`; it also protects the baseline-fairness intent of `RL-D06`.

## 3. Method and Scope

**Evidence.** This pass searched official FHWA publications for the validity boundary of Webster and HCM cycle-length methods and for saturated-condition fixed-time practice: Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm); Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm); and Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 8](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter8.htm).

**Evidence.** The sources were selected because they are official traffic-engineering guidance, not secondary summaries; the FHWA Timing Manual explicitly presents both the Webster equation and the HCM planning-level cycle estimate. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm).

**Inference.** This is a timing-method and baseline-definition pass. It does not establish a site-specific cycle, split, offset, storage limit, or demand plan; those require CADENCE scenario measurements under `TC-D02`.

## Part I — The Standard Cycle-Length Formula Is Not Valid at or Above Saturation

**Evidence.** FHWA presents Webster's minimum-delay cycle formula as \(C=(1.5L+5)/(1-Y)\), identifies it as an isolated-intersection method for random arrivals, and states that the analytical tools developed for cycle-length selection focus on undersaturated flow. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm).

**Evidence.** The same manual states that, when \(Y=1\), the intersection is saturated and the Webster equation is no longer applicable; it further states that oversaturated conditions require special consideration and that these models are not valid in that range. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm).

**Evidence.** FHWA describes the HCM cycle-length expression as a planning-level estimate, says it increases toward a jurisdiction-set maximum as the intersection approaches capacity, and notes that the HCM method does not represent downstream congestion or turn-pocket overflow. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm).

**Inference.** The formula's denominator is zero at \(Y=1\) and negative above it. Capping its numerical output at a maximum cycle produces a feasible timing value, but does not restore the minimum-delay proof or make the plan spillback-aware.

**Inference.** Therefore, neither Webster nor the HCM quick cycle estimate may be called the tuning method for CADENCE's \(v/c\geq1\) fixed-time plan. They remain legitimate screening or initial-plan tools only below saturation.

## Part II — Saturation Changes the Objective Before It Changes the Hardware

**Evidence.** FHWA defines the congested transition operationally by growing residual queues: when demand exceeds capacity and residual queues no longer clear, delay grows with the queue, and when residual queuing begins to grow the intersection has reached maximum throughput. Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm).

**Evidence.** FHWA states that, after maximum throughput can no longer be increased by signal timing, the objective must shift to queue management: arrange signals so queues form where they do the least damage, usually by constraining capacity upstream of the bottleneck where storage will not cause gridlock or safety problems. Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm).

**Evidence.** FHWA's reported saturated-condition strategies include working back from the downstream bottleneck, maximizing useful green for congested movements, phase reservice where feasible, balancing conflicting queues, metering traffic into bottlenecks, and preventing queues from backing into bottlenecks. Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm).

**Evidence.** FHWA separately advises, for congested retiming, reviewing splits and cycle length, changing phasing to avoid turn-bay spillback, and metering entering traffic if other approaches fail so as to avoid upstream spillback, blockage, and turn-bay overflow. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 8](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter8.htm).

**Evidence.** FHWA cautions that long cycles can worsen congestion where downstream capacity is lower than upstream throughput or where turn-bay storage is exceeded; its saturated-condition guidance also rejects the general belief that longer cycles are inherently more efficient. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm); Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm).

**Inference.** The prescribed replacement is not another universal closed-form cycle formula. It is a bottleneck- and storage-aware fixed plan whose stated objective is (1) maximize feasible discharge, then (2) meter and locate unavoidable queues so they do not block critical links or junctions.

## Part III — What a Defensible M3 Fixed-Time Baseline Must Be

**Inference.** A single fixed plan can embody the saturated-condition strategy only for the demand, route, geometry, and bottleneck pattern on which it was designed. It cannot respond to an unexpected full downstream link, so it is a deliberately bounded classical reference, not a spillback-aware controller.

**Proposal.** For undersaturated and near-saturated scenarios, CADENCE should use a fixed plan initialized with Webster/HCM-style critical-flow analysis, then check all safety, pedestrian, minimum-green, clearance, and capacity constraints in the validated SUMO scenario.

**Proposal.** For each oversaturated scenario family, CADENCE should use a separately documented **oversaturated fixed-time queue-management plan**, not a plan described as Webster/HCM-optimised. Its design record should identify the downstream bottleneck, critical storage links, phase sequence, cycle, splits, offsets, any fixed upstream metering, and the intended safe queue-storage locations.

**Proposal.** The saturated fixed plan should first allocate available service to maximize feasible bottleneck discharge; once residual queues cannot be eliminated, it should restrict release toward full or vulnerable downstream links and hold queues at explicitly selected upstream storage locations. Its parameters must remain fixed throughout each run.

**Proposal.** CADENCE should tune every fixed plan using development scenarios only, freeze it before held-out evaluation, and report calibration demand separately from evaluation demand. It must not use runtime queues, detector calls, downstream occupancy, or simulator future state to change the plan.

**Proposal.** M3 reports for fixed-time baselines should include completion/throughput, residual queue or cycle-failure evidence, spillback and junction-blocking events, and the locations of stored queues. Mean delay alone is not a sufficient oversaturated baseline result.

**Inference.** A plan that simply clamps the Webster/HCM cycle length and apportions green by critical flow ratio is not defensible for the required spillback regime, because its method has no valid saturated objective or downstream-storage representation.

## 7. Proposals for M3

### Proposal 1

> Issue a successor decision that supersedes `TC-D04` and states that Webster/HCM critical-flow timing is permitted only for undersaturated or near-saturated fixed-time plan initialization; it is not a valid oversaturated tuning method.

### Proposal 2

> Require an oversaturated fixed-time baseline to be a frozen, scenario-family-specific queue-management plan: document its bottleneck, protected storage links, cycle, splits, offsets, phase sequence, fixed metering choices, and objective of maximizing feasible discharge before locating unavoidable queues safely.

### Proposal 3

> Require fixed-time calibration on development scenarios and frozen evaluation on held-out scenarios; prohibit runtime adaptation and report throughput, residual queue/cycle failure, spillback, junction blocking, and queue location alongside delay.

## 8. Register

| Item | Kind | Bears on | Verdict | Action for Claude |
|---|---|---|---|---|
| Webster/HCM timing validity boundary | evidence | `TC-D04`, M3 | narrows | supersede `TC-D04` with Proposal 1 |
| Saturated-condition objective: throughput, then queue management | evidence | `TC-D01`, `TC-D03`, `CM-D06`, M3 | supports | register Proposal 2 |
| Downstream bottleneck, metering, and anti-spillback practice | evidence | `TC-D03`, `CM-D06`, M3 | supports | register Proposal 2 |
| Proposal 1 | proposal | `TC-D04`, M3 | narrows | register |
| Proposal 2 | proposal | `TC-D03`, `CM-D06`, M3 | supports | register |
| Proposal 3 | proposal | `TC-D01`, `TC-D03`, `CM-D06`, `RL-D06`, M3 | supports | register |
| Exact scenario-specific cycles, splits, offsets, metering thresholds, and storage locations | open question | M3, `TC-D02` | does not reach | defer to calibrated scenario design |

## 9. Evidence Quality and Boundary

**Evidence.** The validity conclusion and saturated-condition recommendations come from official FHWA guidance that directly presents the Webster/HCM methods and the saturated-operation alternative. Koonce et al. (2008), *Traffic Signal Timing Manual*, Federal Highway Administration, FHWA-HOP-08-024, [Chapter 6](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter6.htm); Federal Highway Administration (2009), *Signal Timing Under Saturated Conditions: Guidance*, FHWA-HOP-09-008, [official publication](https://ops.fhwa.dot.gov/publications/fhwahop09008/guidance.htm).

**Inference.** The evidence is sufficient to answer the methodological question: `TC-D04` is not sufficient as written for M3's mandated oversaturation regime. It does not determine the numerical plan for any CADENCE network and does not establish that a static plan can prevent spillback under unanticipated demand changes.
