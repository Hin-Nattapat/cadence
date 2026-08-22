# CADENCE — SUMO and Simulation Foundation Research

**Document Type:** Focused Research Notebook
**Status:** Organised baseline. Targeted research deferred to M0.
**Reserved decision prefix:** `SIM-D`

> **Provenance.** This document was assembled on 2026-08-22 from material that already
> existed in `CADENCE_INITIAL.md` §§7–14, 26, 30. It was reorganised, not extended.
>
> `CADENCE_RESEARCH_STATUS.md` marked this track complete, and both
> `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` §25 and
> `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §34 instructed readers to consult a "SUMO
> research checkpoint" — but no such file existed. The content was real; the file was not.
> That gap is what this document closes.
>
> The remaining depth (§11) is deliberately deferred to M0 so that it is driven by concrete
> implementation questions rather than another open-ended literature pass, per
> `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` §24.

---

# 1. Why the Simulator Comes First

Reinforcement Learning optimises behaviour against whatever environment and reward it is
given. If the simulation contains unrealistic topology, incorrect junction behaviour,
artificial deadlocks, implausible vehicle behaviour, or hidden simulator interventions, an
agent will learn to exploit those artifacts rather than learn traffic control.

> **Do not optimize an environment we do not trust.** (`AP-01`)

The first milestone of CADENCE is therefore not a model. It is a validated simulation
foundation.

---

# 2. Real-World Network Acquisition

OpenStreetMap is the initial source of road-network data; SUMO remains the microscopic
simulator. SUMO supports native OSM import through `netconvert`, and provides scenario
tooling such as `osmWebWizard.py`.

Target workflow:

```
Selected geographic area
        v
Acquire OSM data
        v
Network conversion (netconvert)
        v
Network preprocessing
        v
Junction validation
        v
Traffic-light validation
        v
Route / demand generation
        v
Simulation scenario
```

## Import is not validation

SUMO documentation notes explicitly that imported networks commonly require correction:
roads, turn relationships, lane counts, and traffic lights. Network deficiencies surface
later as unrealistic congestion or vehicle teleportation, which are easily mistaken for
controller failures.

Network validation is therefore a first-class component of the project, not a preparation
step. It becomes the `cadence validate-scenario` tool.

---

# 3. Incremental Network Scaling

Real topology introduces complexity that regular synthetic grids do not have: unequal link
lengths, unequal lane counts, turning lanes, one-way streets, irregular and offset
intersections, asymmetric demand, differing capacities, heterogeneous signal programs.

```
Synthetic single intersection
        v
Real-world single intersection
        v
Real-world corridor (3-5 signals)
        v
Small real-world district (10-30 signals)
        v
Larger urban network
```

The project does not begin with a city. Small real-world networks carry enough complexity
to be scientifically interesting while remaining observable and debuggable.

---

# 4. Artificial Deadlock versus Real Gridlock

Two phenomena look identical in a results table and must be separated.

## 4.1 Artificial simulation deadlock

A defect. Candidate causes:

- incorrect lane connections,
- very short intermediate edges,
- incorrectly separated junctions,
- invalid or unrealistic traffic-light programs,
- route-generation errors,
- implausible lane-changing behaviour,
- inappropriate network-conversion settings.

These are simulation defects and must be corrected before any controller is evaluated.

## 4.2 Real traffic gridlock

Congestion propagating until downstream links have no remaining capacity.

```
J1 -> J2 -> J3
^            v
J6 <- J5 <- J4
```

If every intersection keeps discharging into saturated downstream links, queues propagate
upstream until the network blocks. This is a legitimate traffic-control problem and must
not be removed from the simulator. A network-aware controller is expected to detect and
respond to the conditions that lead to it.

Distinguishing the two is one of the open research questions of the simulation track.

---

# 5. Spillback

Spillback occurs when a downstream queue grows far enough upstream to interfere with the
upstream intersection.

```
Large incoming queue
        v
Controller releases vehicles
        v
Downstream link is already saturated
        v
Vehicles cannot clear the intersection
        v
Queue propagates upstream
        v
Network performance deteriorates
```

A controller observing only its own approaches can make a locally reasonable and globally
harmful decision. This changes the controller's question from

> which direction currently has the most traffic?

to

> which movement can be served without creating harmful downstream congestion?

Observations implied by this framing:

```
Incoming       queue length, waiting time, occupancy, arrival rate
Intersection   current phase, elapsed phase time
Downstream     occupancy, queue length, available capacity
```

The simulator must be able to produce spillback for this research question to exist at all.
This is an explicit item in the definition of done (§9).

---

# 6. Vehicle Behaviour

SUMO is microscopic: individual vehicle behaviour is governed by several behavioural models
and their parameters. These are not cosmetic. They determine queue formation, discharge
rate, intersection capacity, and whether spillback appears at all.

## 6.1 Car-following

Governs response to a leading vehicle: acceleration, deceleration, desired gap, minimum
gap, reaction behaviour, desired speed.

SUMO's default is a modified **Krauss** model; alternatives are supported. The
`actionStepLength` parameter separates simulation step length from the frequency of driver
decision-making.

## 6.2 Lane-changing

Affects route preparation, strategic lane selection, cooperation, speed-gain changes, lane
preference, and bottleneck formation near junctions. SUMO's default is **LC2013**.

---

# 7. Driver Heterogeneity

Real drivers are not identical. A later version of the environment may model behavioural
profiles, conceptually:

```
Aggressive     smaller preferred gap, stronger acceleration, more lane changes
Normal         calibrated baseline
Conservative   larger preferred gap, lower acceleration, less aggressive lane changing
```

These must eventually rest on defensible parameters or empirical calibration. The
simulation foundation begins with controlled SUMO defaults; heterogeneity is introduced
only once baseline behaviour is understood.

---

# 8. Calibration

Real geometry alone does not produce realistic traffic.

Candidate calibration targets:

```
traffic volume · queue length · average travel time · intersection discharge rate
lane utilisation · speed distribution · route distribution · congestion propagation
```

Candidate calibration parameters:

```
demand volume · route choice · vehicle-type distribution
car-following parameters · lane-changing parameters · signal timing
```

Full automatic calibration is not an initial requirement. The initial requirement is that
every important assumption is **explicit, configurable, measurable, and reproducible**.

Related: `TC-D02` requires scenario saturation flow and queue discharge to be validated
before controller evaluation.

---

# 9. Simulation Foundation — Definition of Done

This is the operational payload of this document. It is the acceptance criteria for M0-M1.

- [ ] OSM-derived networks can be generated reproducibly.
- [ ] Road and lane topology can be inspected and validated.
- [ ] Turning connections are correct.
- [ ] Signalised intersections are correctly represented.
- [ ] Traffic-light programs are understandable and controllable.
- [ ] Vehicles generate valid routes.
- [ ] Queues form and discharge plausibly.
- [ ] Lane-changing behaviour introduces no obvious artificial bottleneck.
- [ ] Downstream congestion can produce spillback.
- [ ] Artificial topology-related deadlocks can be identified.
- [ ] Genuine demand-induced gridlock remains possible.
- [ ] SUMO vehicle teleportation is explicitly configured and logged.
- [ ] Random seeds reproduce experiment conditions.
- [ ] Traffic metrics are collected consistently.
- [ ] Fixed-time control produces stable and explainable behaviour.

The last item belongs to M3 under the accepted milestone ladder (`PD-D02`); the rest belong
to M0-M1.

---

# 10. Open Research Questions — Simulation Track

1. How reliably can OSM-derived SUMO networks represent real intersection topology?
2. Which imported-network defects most strongly affect congestion behaviour?
3. Which SUMO vehicle parameters most strongly influence queue formation and spillback?
4. How should heterogeneous driver behaviour be represented?
5. How can artificial simulation deadlock be distinguished from legitimate gridlock?
6. How should SUMO teleportation be configured and interpreted during experiments?

---

# 11. Targeted Research Deferred to M0

Deliberately not answered in advance. Each item is expected to be resolved by a concrete
implementation question during M0, and recorded here with a `SIM-D` identifier.

| Topic | Why it is needed |
|---|---|
| `libsumo` versus TraCI semantics and behavioural differences | `PD-D03` makes the binding switchable; the two must be verified to produce identical results, or the differences documented |
| Teleport configuration and interpretation | required by the definition of done, and a headline failure metric |
| Queue and detector measurement definitions in SUMO | `halting` thresholds, detector semantics, and how they map to `LaneState` and `MP-D04` |
| Seeding and determinism guarantees | `AP-06`; also the basis of `cadence verify-run` |
| OSM preprocessing pitfalls | lane counts, turn restrictions, signal tagging, junction merging |
| Left-hand traffic network construction | needed only if `PD-Q01` selects a Thai site |
| Sublane model and lateral resolution | needed only if motorcycle-dense traffic is pursued; see `PD-Q01` |

---

# 12. Decision Register

No `SIM-D` decision has been issued yet. Identifiers are allocated during M0 and recorded
in `research/decisions.yaml`.

---

# 13. References

1. Eclipse SUMO — OpenStreetMap Import
   https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html
2. Eclipse SUMO — Import from OpenStreetMap Tutorial
   https://sumo.dlr.de/docs/Tutorials/Import_from_OpenStreetMap.html
3. Eclipse SUMO — Scenario Guide
   https://sumo.dlr.de/docs/Tutorials/ScenarioGuide.html
4. Eclipse SUMO — Vehicle Types and Routes
   https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html
5. Eclipse SUMO — Car-Following Models
   https://sumo.dlr.de/docs/Car-Following-Models/index.html
6. Original university project
   https://github.com/Hin-Nattapat/Reinforcement_Traffic_Project
