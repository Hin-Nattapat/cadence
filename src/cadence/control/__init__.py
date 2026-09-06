"""The signal safety layer: what a controller may ask for, and what may reach the simulator.

CONTRACT: a controller requests, this layer decides (ARCH-D04). Nothing here imports
cadence.simulation.sumo -- the layer is a pure state machine over canonical domain state
and emits commands as data, which exactly one module under simulation/sumo applies
(SIG-D04, the R3 and R4 fences in tests/test_architecture.py).
"""
