# Addendum — Shared-Lane Queues and Turn-Ratio Evidence for M1b

**Research question.** When one lane serves multiple turning movements, how does
Max-Pressure attribute its queue to individual movements, what turn-ratio
estimators does it use, and is the service-conditioned discharge-sampling bias
published?

**Scope and method.** One targeted pass of publisher pages, official proceedings,
and official university publication records, limited to peer-reviewed/proceedings
papers and one labelled preprint where the published record is also available.
Bibliographic metadata below was checked against the publisher/proceedings or
official university record. No scenario-demand data were treated as runtime
evidence.

## Findings

### 1. Original Max-Pressure does not derive movement queues from a shared-lane count

**Evidence.** Varaiya's original formulation has a separate, unbounded point queue
for every turn movement. It assumes fixed turn ratios; its adaptive version may use
measured turn movements and saturation rates. It therefore does not specify a rule
that splits one observed shared-lane queue among its possible movements.

Source: Varaiya, P. (2013). “Max pressure control of a network of signalized
intersections.” *Transportation Research Part C: Emerging Technologies*, 36,
177–195. DOI: [10.1016/j.trc.2013.08.014](https://doi.org/10.1016/j.trc.2013.08.014).

**Inference.** A lane-level proportional split is a state-estimation substitution,
not Original Max-Pressure. It needs its own version and must not inherit the
original movement-queue stability claim.

### 2. An established alternative avoids the split and the turn ratios

**Evidence.** Gregoire et al. identify the same physical mismatch: vehicles for
straight/left/right movements can be gathered in one lane while cameras provide
only an aggregate queue. Their alternative back-pressure controller uses aggregate
queue estimates plus stop-line loop detectors for each possible direction; it does
not require routing rates. This is a different controller, not an estimator that
recovers individual movement queues from the aggregate.

Source: Gregoire, J., Frazzoli, E., de La Fortelle, A., & Wongpiromsarn, T.
(2014). “Back-pressure traffic signal control with unknown routing rates.”
*IFAC Proceedings Volumes*, 47(3), 11332–11337. DOI:
[10.3182/20140824-6-ZA-1003.01585](https://doi.org/10.3182/20140824-6-ZA-1003.01585).

### 3. Published Max-Pressure turn-ratio treatment is assumption-level, not one standard online estimator

**Evidence.** Le et al. prove their cyclic BackPressure policy retains its stability
result with any *unbiased* turning-fraction estimator. The paper's available
publisher record does not prescribe a sliding-window discharged-count algorithm.
Its cyclic policy allocates strictly positive service time to every phase in each
control decision, which removes the literal “never green” case in that model.

Source: Le, T., Kovacs, P., Walton, N., Vu, H. L., Andrew, L. L. H., &
Hoogendoorn, S. P. (2015). “Decentralized signal control for urban road
networks.” *Transportation Research Part C: Emerging Technologies*, 58(C),
431–450. DOI: [10.1016/j.trc.2014.11.009](https://doi.org/10.1016/j.trc.2014.11.009).

**Evidence.** Zoabi and Haddad explicitly identify both shared-lane handling and
downstream turn-ratio estimation as omissions in earlier queue-based Max-Pressure
formulations. They introduce a lane-structured controller and a revised turn-ratio
update mechanism. The accessible publisher and official university records do not
expose enough method detail to identify that update mechanism as a discharged-count
sliding window or to verify its treatment of service opportunity.

Source: Zoabi, R., & Haddad, J. (2026). “Enhanced queue-based Max-Pressure
traffic signal control.” *Transportation Research Part C: Emerging Technologies*,
186, Article 105538. DOI:
[10.1016/j.trc.2026.105538](https://doi.org/10.1016/j.trc.2026.105538).
Publication status and metadata: [Technion official record](https://cris.technion.ac.il/en/publications/enhanced-queue-based-max-pressure-traffic-signal-control/).

### 4. The reported discharged-observation bias is not resolved by the sources found

**Open question.** In this pass, no eligible Max-Pressure paper was found that
explicitly analyses the following feedback bias or gives an estimator correction
for it: a movement with little/no green yields few/no discharge observations; a
turn-ratio estimate constructed from those observed discharges then assigns that
movement less share; the controller can consequently continue to deprioritise it.
This is distinct from (a) the original per-movement-queue assumption, (b) unknown-
routing alternatives, (c) unbiased-estimator assumptions, and (d) the
shared-lane/turn-ratio structural limitations identified by Zoabi and Haddad.

**Inference.** For an estimator

```text
r_hat(m) = D(m) / sum_j D(j)
```

over a window, no discharge for movement `m` while other movements discharge makes
`r_hat(m) = 0`. If a positive pseudo-count prior is used instead, its share still
tends to zero as observed discharges of other movements grow. This estimates a
service-observed discharge mix, not latent arrival intentions, unless the sampling
mechanism is demonstrably representative of arrivals. This algebra establishes the
failure mode; it is not a published Max-Pressure result.

## M1b decision proposals

### `movement_queue_proportional_split_v1`

**Decision proposal.** Define the output as an *estimated movement queue*:

```text
q_hat(lane, movement) = q_lane × r_hat(lane, movement)
```

for the movements legally reachable from that lane, with the conservation invariant
that their estimates sum to the lane estimate. Version it separately from
`movement_definition_v1`; mark its source as estimated and do not label it Original
Max-Pressure. This is the smallest transparent M1b mapping, not a claim to model
shared-lane FIFO ordering or front-vehicle blocking.

**Open question.** A lane-structured/FIFO-aware controller is the literature-backed
direction for higher fidelity, but it is not needed to define this explicit M1b
estimator and its accessible 2026 formulation was insufficient to reproduce.

### `turn_ratio_sliding_window_v1`

**Decision proposal.** If M1b uses completed traversal/discharge events in a
look-back window, name the result a **service-observed turn proportion** in the
schema and documentation, not an arrival turn ratio. Record at least window length,
event count per movement, oldest/newest event time, configured prior, and whether a
movement had a service opportunity. Do not read scenario demand proportions.

**Decision proposal.** Preserve configured prior support for a movement with no
service opportunity in the evidence window; absence of discharge alone must not
erase its support. This is a CADENCE safeguard derived from the inference above,
not a literature-derived proof of unbiasedness.

**Open question.** The exact exposure-aware update rule is unresolved. A green flag,
effective-green duration, discharge capacity, and queue-at-stop-line observation
answer different questions. Resolve it only with a separately sourced estimator
model or with explicitly scoped M1b experiment evidence; do not represent v1 as an
estimator of latent arrival intent under saturation.

## Evidence quality and boundary

- **High:** Original movement-specific queue assumption; published aggregate-queue
  unknown-routing alternative; Le et al.'s unbiased-estimator condition; 2026
  peer-reviewed paper's explicit shared-lane and turning-ratio scope.
- **Medium:** Exact mechanics of the 2026 revised update mechanism, because its
  accessible official records provide the abstract/section outline but not the full
  formula.
- **Not established:** A published Max-Pressure treatment of the service-conditioned
  discharged-count feedback bias. The result is deliberately an open question.
