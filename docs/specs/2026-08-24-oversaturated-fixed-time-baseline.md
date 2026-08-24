# Oversaturated Fixed-Time Baseline

**Status:** adopted
**Date:** 2026-08-24
**Supersedes:** `TC-D04`
**Evidence:** `research/addenda/2026-08-24-oversaturated-fixed-time-baseline.md`

## 1. Why this exists

`TC-D04` said the fixed-time baseline "should be reasonably tuned using established
traffic-engineering principles". Read naturally, the established principle for cycle length
and green splits is Webster's formula and its Highway Capacity Manual descendants.

FHWA's own manual states that those methods stop working exactly where CADENCE's research
question lives:

> If Y = 1, the intersection is saturated and the equation is no longer applicable.

> Oversaturated conditions require special considerations, and these models are not valid
> during that range of conditions.

Webster's denominator is `1 - Y`. At `Y = 1` it is zero; above it, negative. Capping the
output at a maximum cycle still yields a number, but it is no longer a minimum-delay result
and it is not spillback-aware.

`TC-D01`, `TC-D03`, and `CM-D06` all require evaluation under oversaturation and spillback.
So `TC-D04`, followed literally, would have produced a baseline tuned by an inapplicable
formula in precisely the regimes the project exists to study — and every RL comparison
against it would have been a comparison against a straw man. That is the failure `RL-D06`
was written to prevent, arriving through a different door.

The three decisions below replace it. They were proposed by the Research Agent from the
sources in the addendum, and adopted here by the maintainer.

## 2. Decisions

### `TC-D09`

> Webster and HCM critical-flow timing are permitted only to initialise an undersaturated
> or near-saturated fixed-time plan. They are not a valid tuning method at or above
> saturation, and no CADENCE fixed-time plan for regime C or D may be described as tuned
> by them.

### `TC-D10`

> An oversaturated fixed-time baseline is a frozen, scenario-family-specific queue
> management plan. It documents its bottleneck, its protected storage links, and its cycle,
> splits, offsets, phase sequence and any fixed metering, and it states its objective:
> maximise feasible discharge first, then place unavoidable queues where they do least
> damage.

### `TC-D11`

> Fixed-time plans are calibrated on development scenarios and frozen for evaluation on
> held-out scenarios, with no runtime adaptation. Results report throughput, residual queue
> and cycle failure, spillback, junction blocking, and queue location alongside delay.

## 3. What this does not settle

Cycle lengths, splits, offsets, metering thresholds, and storage locations are scenario
properties, not decisions. They follow from calibrating a scenario under `TC-D02` and are
recorded as experiment metadata, not here.

`TC-D10` describes a plan that embodies a saturated-condition strategy for the demand and
geometry it was designed against. It cannot respond to an unexpected full downstream link.
That is intended: it is a bounded classical reference, not a spillback-aware controller.
