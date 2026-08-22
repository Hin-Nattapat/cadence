# CADENCE — Origin

**Document Type:** Background. Rarely changes.

This document records why CADENCE exists and what was learned from the project it revisits.
It is deliberately separate from current planning: `docs/DIRECTION.md` changes often, this
does not.

---

# 1. The 2020 Project

CADENCE revisits a university graduation project,
[`Reinforcement_Traffic_Project`](https://github.com/Hin-Nattapat/Reinforcement_Traffic_Project)
(2020, 211 commits), which explored Reinforcement Learning for traffic signal control using
SUMO and TraCI.

It already contained real foundations:

- SUMO microscopic traffic simulation,
- TraCI-based traffic-light control,
- fixed-time signal baselines,
- reinforcement-learning controllers,
- multi-intersection synthetic networks,
- measurement of waiting time, queue length, flow, speed, and density.

It demonstrated the concept. It did not achieve the intended result. Limitations in the
simulation design, traffic-state representation, controller design, and implementation
prevented it, and the most visible symptom was **deadlock in larger synthetic grid
networks**.

CADENCE is not a rewrite of that implementation. The original is preserved as a historical
baseline. The environment is rebuilt from first principles.

---

# 2. The Governing Conclusion

The central lesson is that improving the RL algorithm alone would not have helped.

> **Do not optimize an environment we do not trust.**

Reinforcement Learning optimises against whatever environment and reward it is given. An
agent in a simulator with unrealistic topology, incorrect junction behaviour, artificial
deadlocks, or hidden interventions will learn to exploit those artifacts. In 2020 the
simulator was never separately validated, so there was no way to tell a controller failure
from an environment defect.

Simulator first, controller second. This is `AP-01`, and it is the reason M0-M3 contain no
learning at all.

---

# 3. Five Specific Lessons

## 3.1 Traffic state was shaped around the controller

State was represented in terms of the movements the controller could select, rather than
describing the traffic condition. The controller's action space leaked into the
representation of the world.

CADENCE separates them explicitly:

```
SUMO environment state
        v
Observation builder
        v
Controller observation
```

Now `ARCH-D03`.

## 3.2 RL and heuristics were entangled

The original controller mixed learned decisions with hand-written logic for selecting
movements and computing signal duration. When the result was poor, the cause could not be
attributed.

Heuristic control remains valuable in CADENCE, but as an explicit named baseline
controller, never hidden inside a learned one. Responsibilities are separated:

```
Observation -> Controller -> Requested action -> Safety layer -> Executed transition
```

Now `ARCH-D04` and `AP-04`.

## 3.3 Reward was not treated as a design surface

The first reward function must remain interpretable. A conceptual starting point:

```
reward = -alpha * queue_length - beta * waiting_time - gamma * stops
```

Later terms may include throughput, spillback penalty, downstream blocking, phase-switch
penalty, fairness, and maximum waiting. Complexity is added only when an experiment
justifies it, and reward is never the experiment KPI.

Now `ARCH-D05` and `RL-D04`.

## 3.4 Metrics were cumulative from episode start

Observations and rewards used running averages accumulated from the beginning of an
episode, which makes a controller's recent behaviour nearly invisible in its own signal.

CADENCE uses current values or bounded windows:

```
queue length now
lane occupancy now
vehicles passed during the last dt
waiting accumulated during the last dt
```

Now `PD-D04` rule R4.

## 3.5 Neighbouring intersections were not represented

The 2020 project ran multiple intersections, but each controller saw only itself.
Downstream and neighbouring state was never in the observation, which is precisely the
information needed to avoid discharging into a link that cannot accept vehicles.

This absence is the origin of the entire current research direction. It is why the project
is called *network-aware*, and why spillback and finite downstream storage — not RL — are
the subject of Study 1.

---

# 4. What CADENCE Is Trying to Settle

The question the 2020 project asked and could not answer:

> **What happens to the surrounding network if this intersection releases these vehicles
> now?**

Answering it credibly requires a simulator that can be trusted, baselines strong enough
that beating them means something, and a controller interface that lets different methods
compete on equal terms. That is the platform. The controller is what runs on it.

---

# 5. The Name

**CADENCE** is a codename, not an acronym.

It refers to rhythm, timing, and coordinated movement. A traffic controller is not merely
switching lights; it is regulating the cadence of vehicle movement across an interconnected
network.

Technical components, variables, modules, and terminology use established
traffic-engineering and machine-learning vocabulary, never CADENCE-specific coinages.

---

# 6. Related Documents

| Document | Contains |
|---|---|
| `docs/DIRECTION.md` | current status, milestone ladder, scenarios, non-goals |
| `docs/specs/2026-08-22-project-direction.md` | the decisions that set the current direction |
| `research/INDEX.md` | the research corpus and what each track concluded |
| `research/decisions.yaml` | every decision identifier in the project |
