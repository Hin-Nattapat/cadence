#!/usr/bin/env bash
# verify-m2-signal-contract.sh — the map's §5. One line per §4 row (and R2's anchor).
# Silent when green; prints FAIL/ASK lines otherwise. Decision ids are checked separately by
# tools/check_decisions.py inside `make check`.
cd "$(dirname "$0")" || exit 0
. ./chk.sh

chk P3 "tls_program carries min/max duration columns the static program cannot fill" ../../src/cadence/simulation/artifacts.py 'min_duration_s'
chk P4 "s0 has a 3 s yellow phase and no all-red" ../../scenarios/s0_turning/v1/network.net.xml 'duration="3"  state="yyyyrrrryyyyrrrr"'
chk P8 "controlled-link index is the state-string index" ../../src/cadence/simulation/sumo/topology_reader.py 'getControlledLinks(tls_id)'
chk R2 "the lamp fence still points the safety layer at control/" ../../tests/test_architecture.py 'SIGNAL_SAFETY_LAYER = SRC_ROOT / "control"'

chk P1 "online program measured and recorded" ../../research/decisions.yaml 'SIM-D01:'
chk P2 "getSpentDuration behaviour measured and recorded" ../../research/decisions.yaml 'SIM-D01:'
chk P6 "setPhase semantics measured and recorded" ../../research/decisions.yaml 'SIM-D02:'
chk P7 "binding parity on TLS writes measured and recorded" ../../research/decisions.yaml 'SIM-D03:'
chk P9 "timeout answer recorded as a decision" ../../research/decisions.yaml 'SIG-D07:'

chk_summary
