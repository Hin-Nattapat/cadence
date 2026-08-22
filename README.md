# CADENCE

**A controller-agnostic platform for network-aware adaptive traffic signal control on
real-world road networks.**

Most adaptive signal controllers optimise the intersection in front of them. CADENCE exists
to study the question they cannot ask:

> **What happens to the surrounding network if this intersection releases these vehicles
> now?**

The regimes that matter here are oversaturation and spillback — where releasing a queue
into a link that cannot accept it converts a local decision into network-wide congestion.

CADENCE is built around a validated SUMO simulation core with a stable controller contract,
so that fixed-time, actuated, Max-Pressure, predictive, and learned controllers can be
compared on identical networks, demand, safety constraints, and metrics.

> **Status: pre-implementation.** Research and architecture are complete; the codebase is
> being built from M0. See [`docs/DIRECTION.md`](docs/DIRECTION.md).

---

## Principles

| | |
|---|---|
| **Environment first** | Do not optimise an environment we do not trust. The simulator is validated before any performance claim. |
| **Controller-agnostic** | The simulation core has no dependency on any control method. Controllers are plugins. |
| **Domain API over simulator API** | The simulator knows SUMO; controllers know traffic control. |
| **Shared safety layer** | Controllers request actions. The environment owns legal signal transitions. |
| **Objective separate from evaluation** | A controller's reward or cost is private to it. Experiment KPIs are computed independently. |
| **Reproducible by construction** | Scenario, seed, network, demand, controller config, and software versions are explicit experiment metadata. |

---

## Controllers

| Controller | Status |
|---|---|
| Fixed-time (tuned) | planned — M3 |
| SUMO native actuated | planned — M3 |
| PPO | planned — M5 |
| DQN | planned — M5 |
| Max-Pressure | planned — M8 |
| Capacity-aware pressure | supported, unscheduled |
| MPC | supported, unscheduled |
| MARL / GNN | supported, unscheduled |

---

## Studies

Research questions run *on* the platform, and are versioned separately from it.

### Study 1 — Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks

Revisits a 2020 university graduation project
([`Reinforcement_Traffic_Project`](https://github.com/Hin-Nattapat/Reinforcement_Traffic_Project))
with current tooling and a simulator that can be trusted. The original demonstrated the
concept but could not achieve its intended result, and deadlocked on larger networks.

Background: [`docs/ORIGIN.md`](docs/ORIGIN.md)

---

## Repository

```
CLAUDE.md                  working rules, conventions, test strategy
docs/
  ORIGIN.md                why the project exists; lessons from 2020
  DIRECTION.md             current status, milestones, scenarios, non-goals
  specs/                   dated decision records
research/
  INDEX.md                 the research corpus and what each track concluded
  decisions.yaml           every decision identifier in the project
  CADENCE_*.md             focused research notebooks
scenarios/<id>/v<N>/       versioned scenario definitions
studies/<NN>-<slug>/       experiments and their results
```

---

## Built With

Python 3.12 · [Eclipse SUMO](https://sumo.dlr.de/) 1.27.1 · Gymnasium ·
Stable-Baselines3 · uv · ruff · mypy · pytest

---

## License

Not yet chosen.
