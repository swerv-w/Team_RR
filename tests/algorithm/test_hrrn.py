"""
HRRN (Highest Response Ratio Next) Scheduling Algorithm - Test Cases
=====================================================================

System Properties:
  - E core: processes 1 unit/sec, consumes 1W/sec, startup cost 0.1W
  - P core: processes 2 units/sec, consumes 3W/sec, startup cost 0.5W
  - Scheduling granularity: 1 second (no fractional splits)
  - P core: even if remaining work = 1, still takes 1 full second

Finalized Policies (team decision):
  1. Idle power   : Startup cost occurs only ONCE per core (first activation).
                    Idle intervals consume 0W (core stays warm, no re-startup).
  2. Core assignment (multi-core):
                    Highest Response Ratio -> P core first.
                    Ties broken by PID ascending.
                    Remaining processes fill E cores in ratio-descending order.
  3. NTT denominator: logical burst_time (NOT actual wall-clock duration).
                    NTT = turnaround_time / burst_time

HRRN Formula:
  Response Ratio = (waiting_time + burst_time) / burst_time
  Non-preemptive: ratio computed at each dispatch point (1-sec ticks)

NOTE: burst_time = logical work units.
      P core processes 2 units/sec -> actual_duration = ceil(burst_time / 2)
      E core processes 1 unit/sec  -> actual_duration = burst_time
"""

import pytest
from dataclasses import dataclass
from typing import List, Tuple
from models.core_config import CoreConfig
from models.process import Process
from models.sim_config import SimConfig
from algorithms.hrrn import schedule, calculate_power


# ---------------------------------------------------------------------------
# Data structures (mirrors the shared project architecture)
# ---------------------------------------------------------------------------

@dataclass
class Process:
    pid: int
    arrival_time: int
    burst_time: int          # logical work units
    remaining_time: int = 0
    start_time: int = -1
    finish_time: int = -1
    waiting_time: int = 0
    turnaround_time: int = 0
    response_time: int = 0
    normalized_turnaround_time: float = 0.0

    def __post_init__(self):
        if self.remaining_time == 0:
            self.remaining_time = self.burst_time


@dataclass
class CoreConfig:
    num_p_cores: int
    num_e_cores: int

    @property
    def total_cores(self):
        return self.num_p_cores + self.num_e_cores

    P_CORE_RUN_POWER = 3.0
    E_CORE_RUN_POWER = 1.0
    P_CORE_STARTUP   = 0.5   # one-time, first activation only
    E_CORE_STARTUP   = 0.1   # one-time, first activation only
    # Policy 1 finalized: idle gap -> 0W (warm standby, no re-startup)
    P_CORE_IDLE      = 0.0
    E_CORE_IDLE      = 0.0
    P_CORE_SPEED     = 2
    E_CORE_SPEED     = 1


@dataclass
class TestCase:
    name: str
    description: str
    cores: CoreConfig
    processes: List[Process]
    expected_gantt: List[Tuple]   # (pid, core_id, start, end)
    expected_wt:    List[int]     # indexed by pid-1
    expected_tt:    List[int]
    expected_ntt:   List[float]   # NTT = TT / logical_burst_time
    expected_power: float
    notes: str = ""


# 기존
def make_procs(data: List[Tuple]) -> List[Process]:
    return [Process(pid=d[0], arrival_time=d[1], burst_time=d[2]) for d in data]


# ===========================================================================
# TEST CASE DEFINITIONS  (hand-calculated with finalized policies)
# ===========================================================================

# ---------------------------------------------------------------------------
# TC-01  Basic single E-core — tie-breaking by PID
# ---------------------------------------------------------------------------
# Setup: 1 E core, 3 processes
#   P1: arrival=0, burst=5
#   P2: arrival=2, burst=3
#   P3: arrival=4, burst=1
#
# Trace:
#   t=0 : P1 only -> dispatch P1 (t0~t5)
#   t=5 : P2 ratio=(3+3)/3=2.0,  P3 ratio=(1+1)/1=2.0  -> tie -> PID asc -> P2
#          dispatch P2 (t5~t8)
#   t=8 : P3 only -> dispatch P3 (t8~t9)
#
# Results:
#   P1: WT=0, TT=5,  NTT=5/5=1.00
#   P2: WT=3, TT=6,  NTT=6/3=2.00
#   P3: WT=4, TT=5,  NTT=5/1=5.00
#
# Power: startup 0.1 + 9sec*1W = 9.1W
#
TC01 = TestCase(
    name="TC-01",
    description="Basic single E-core HRRN: tie-breaking by PID",
    cores=CoreConfig(num_p_cores=0, num_e_cores=1),
    processes=make_procs([(1,0,5),(2,2,3),(3,4,1)]),
    expected_gantt=[(1,"E0",0,5),(2,"E0",5,8),(3,"E0",8,9)],
    expected_wt=[0, 3, 4],
    expected_tt=[5, 6, 5],
    expected_ntt=[1.00, 2.00, 5.00],
    expected_power=9.1,
    notes="Tie at t=5: ratio=2.0 for both P2 and P3. Lower PID wins."
)

# ---------------------------------------------------------------------------
# TC-02  HRRN ratio inversion — starvation prevention
# ---------------------------------------------------------------------------
# Setup: 1 E core, 3 processes
#   P1: arrival=0, burst=8
#   P2: arrival=1, burst=2
#   P3: arrival=1, burst=6
#
# Trace:
#   t=0 : P1 only -> dispatch P1 (t0~t8)
#   t=8 : P2 ratio=(7+2)/2=4.50, P3 ratio=(7+6)/6=2.17 -> P2 wins
#          dispatch P2 (t8~t10)
#   t=10: P3 only -> dispatch P3 (t10~t16)
#
# Results:
#   P1: WT=0, TT=8,  NTT=8/8=1.00
#   P2: WT=7, TT=9,  NTT=9/2=4.50
#   P3: WT=9, TT=15, NTT=15/6=2.50
#
# Power: 0.1 + 16*1 = 16.1W
#
TC02 = TestCase(
    name="TC-02",
    description="HRRN ratio inversion: long-waiting short job beats newly-ready long job",
    cores=CoreConfig(num_p_cores=0, num_e_cores=1),
    processes=make_procs([(1,0,8),(2,1,2),(3,1,6)]),
    expected_gantt=[(1,"E0",0,8),(2,"E0",8,10),(3,"E0",10,16)],
    expected_wt=[0, 7, 9],
    expected_tt=[8, 9, 15],
    expected_ntt=[1.00, 4.50, 2.50],
    expected_power=16.1,
    notes="Core HRRN property: equal wait time -> shorter burst wins (higher ratio)."
)

# ---------------------------------------------------------------------------
# TC-03  All processes arrive simultaneously
# ---------------------------------------------------------------------------
# Setup: 1 E core, 4 processes, all at t=0
#   P1:burst=4, P2:burst=2, P3:burst=6, P4:burst=1
#
# t=0 : all ratio=1.0 -> PID order -> P1 (t0~t4)
# t=4 : P4=(4+1)/1=5.0, P2=(4+2)/2=3.0, P3=(4+6)/6=1.67 -> P4 (t4~t5)
# t=5 : P2=(5+2)/2=3.5, P3=(5+6)/6=1.83 -> P2 (t5~t7)
# t=7 : P3 only (t7~t13)
#
# Results:
#   P1: WT=0, TT=4,  NTT=4/4=1.00
#   P2: WT=5, TT=7,  NTT=7/2=3.50
#   P3: WT=7, TT=13, NTT=13/6=2.17
#   P4: WT=4, TT=5,  NTT=5/1=5.00
#
# Power: 0.1 + 13*1 = 13.1W
#
TC03 = TestCase(
    name="TC-03",
    description="All arrive at t=0: initial ratio=1 -> PID tie-break, then HRRN",
    cores=CoreConfig(num_p_cores=0, num_e_cores=1),
    processes=make_procs([(1,0,4),(2,0,2),(3,0,6),(4,0,1)]),
    expected_gantt=[(1,"E0",0,4),(4,"E0",4,5),(2,"E0",5,7),(3,"E0",7,13)],
    expected_wt=[0, 5, 7, 4],
    expected_tt=[4, 7, 13, 5],
    expected_ntt=[1.00, 3.50, round(13/6, 2), 5.00],
    expected_power=13.1,
    notes="At t=0 all ratios equal; PID order applies. HRRN takes over from t=4."
)

# ---------------------------------------------------------------------------
# TC-04  Single P core — 2x speed, ceiling rule, NTT uses logical burst
# ---------------------------------------------------------------------------
# Setup: 1 P core (speed=2), 3 processes
#   P1: arrival=0, burst=4 -> actual_duration = 4/2 = 2sec
#   P2: arrival=1, burst=3 -> actual_duration = ceil(3/2) = 2sec
#   P3: arrival=3, burst=6 -> actual_duration = 6/2 = 3sec
#
# Trace:
#   t=0 : P1 only -> P1 on P0 (t0~t2)
#   t=2 : P2 only (arrived t=1) -> P2 on P0 (t2~t4)
#   t=4 : P3 only -> P3 on P0 (t4~t7)
#
# Results (NTT = TT / logical_burst_time -- POLICY 3 FINALIZED):
#   P1: WT=0, TT=2, NTT=2/4=0.50   <- NTT < 1.0 is valid on P core
#   P2: WT=1, TT=3, NTT=3/3=1.00
#   P3: WT=1, TT=4, NTT=4/6=0.67
#
# Power:
#   Startup: 0.5W (once)
#   Running: 7sec * 3W = 21.0W
#   Total  : 21.5W
#
TC04 = TestCase(
    name="TC-04",
    description="Single P core: 2x speed, ceiling rule, NTT = TT / logical_burst",
    cores=CoreConfig(num_p_cores=1, num_e_cores=0),
    processes=make_procs([(1,0,4),(2,1,3),(3,3,6)]),
    expected_gantt=[(1,"P0",0,2),(2,"P0",2,4),(3,"P0",4,7)],
    expected_wt=[0, 1, 1],
    expected_tt=[2, 3, 4],
    expected_ntt=[round(2/4,2), round(3/3,2), round(4/6,2)],
    expected_power=21.5,
    notes=(
        "NTT = TT / logical_burst (policy 3). "
        "NTT < 1.0 is valid for P core (processes 2 units/sec). "
        "P2 burst=3: ceil(3/2)=2 actual seconds (1 unit capacity wasted)."
    )
)

# ---------------------------------------------------------------------------
# TC-05  Multi-core (1P+1E) — highest-ratio -> P core  [POLICY 2]
# ---------------------------------------------------------------------------
# Setup: 1 P core + 1 E core, 4 processes
#   P1: arrival=0, burst=4
#   P2: arrival=0, burst=2
#   P3: arrival=2, burst=5
#   P4: arrival=2, burst=3
#
# t=0 : P1,P2 ratio=1.0 -> tie -> PID asc -> P1 to P core, P2 to E core
#        P1 on P0: ceil(4/2)=2sec (t0~t2)
#        P2 on E0: 2sec           (t0~t2)
#
# t=2 : Both cores free. P3,P4 arrived.
#        P3 ratio=(0+5)/5=1.0, P4 ratio=(0+3)/3=1.0 -> tie -> P3 to P core, P4 to E core
#        P3 on P0: ceil(5/2)=3sec (t2~t5)
#        P4 on E0: 3sec           (t2~t5)
#
# t=5 : All done.
#
# Results:
#   P1: WT=0, TT=2, NTT=2/4=0.50
#   P2: WT=0, TT=2, NTT=2/2=1.00
#   P3: WT=0, TT=3, NTT=3/5=0.60
#   P4: WT=0, TT=3, NTT=3/3=1.00
#
# Power:
#   P0: startup 0.5 + 5sec*3W = 15.5W
#   E0: startup 0.1 + 5sec*1W =  5.1W
#   Total: 20.6W
#
TC05 = TestCase(
    name="TC-05",
    description="Multi-core (1P+1E): highest-ratio to P core; all start immediately",
    cores=CoreConfig(num_p_cores=1, num_e_cores=1),
    processes=make_procs([(1,0,4),(2,0,2),(3,2,5),(4,2,3)]),
    expected_gantt=[
        (1,"P0",0,2),(2,"E0",0,2),
        (3,"P0",2,5),(4,"E0",2,5),
    ],
    expected_wt=[0, 0, 0, 0],
    expected_tt=[2, 2, 3, 3],
    expected_ntt=[round(2/4,2), round(2/2,2), round(3/5,2), round(3/3,2)],
    expected_power=20.6,
    notes=(
        "Policy 2: highest-ratio -> P core. Equal ratios -> lower PID to P core. "
        "NTT < 1.0 valid for P core processes."
    )
)

# ---------------------------------------------------------------------------
# TC-06  Multi-core (2E) with HRRN contention at core-free events
# ---------------------------------------------------------------------------
# Setup: 2 E cores, 5 processes
#   P1: arrival=0, burst=6
#   P2: arrival=0, burst=4
#   P3: arrival=1, burst=2
#   P4: arrival=1, burst=8
#   P5: arrival=3, burst=1
#
# t=0 : P1,P2 ratio=1.0 -> tie -> P1->E0(t0~t6), P2->E1(t0~t4)
# t=4 : E1 free. P3(wait=3),P4(wait=3),P5(wait=1) in queue.
#        P3=(3+2)/2=2.50, P4=(3+8)/8=1.375, P5=(1+1)/1=2.00 -> P3 wins
#        P3 -> E1 (t4~t6)
# t=6 : E0,E1 free. P4(wait=5),P5(wait=3).
#        P4=(5+8)/8=1.625, P5=(3+1)/1=4.00 -> P5 wins
#        P5->E0(t6~t7), P4->E1(t6~t14)
# t=14: All done.
#
# Results:
#   P1: WT=0, TT=6,  NTT=6/6=1.00
#   P2: WT=0, TT=4,  NTT=4/4=1.00
#   P3: WT=3, TT=5,  NTT=5/2=2.50
#   P4: WT=5, TT=13, NTT=13/8=1.625
#   P5: WT=3, TT=4,  NTT=4/1=4.00
#
# Power (E cores, each activated once, startup cost 1x only):
#   E0: 0.1 + 7*1  =  7.1W
#   E1: 0.1 + 14*1 = 14.1W
#   Total: 21.2W
#
TC06 = TestCase(
    name="TC-06",
    description="Multi-core (2E) HRRN contention: ratio competition when core freed",
    cores=CoreConfig(num_p_cores=0, num_e_cores=2),
    processes=make_procs([(1,0,6),(2,0,4),(3,1,2),(4,1,8),(5,3,1)]),
    expected_gantt=[
        (1,"E0",0,6),(2,"E1",0,4),
        (3,"E1",4,6),
        (5,"E0",6,7),(4,"E1",6,14),
    ],
    expected_wt=[0, 0, 3, 5, 3],
    expected_tt=[6, 4, 5, 13, 4],
    expected_ntt=[1.00, 1.00, 2.50, round(13/8,3), 4.00],
    expected_power=21.2,
    notes="Startup cost per core is one-time only; idle gaps cost 0W (policy 1)."
)

# ---------------------------------------------------------------------------
# TC-07  Edge case: single process
# ---------------------------------------------------------------------------
TC07 = TestCase(
    name="TC-07",
    description="Edge case: single process, no scheduling decision needed",
    cores=CoreConfig(num_p_cores=0, num_e_cores=1),
    processes=make_procs([(1,0,3)]),
    expected_gantt=[(1,"E0",0,3)],
    expected_wt=[0],
    expected_tt=[3],
    expected_ntt=[1.00],
    expected_power=3.1,
)

# ---------------------------------------------------------------------------
# TC-08  Idle gap — startup cost once, idle = 0W  [POLICY 1 FINALIZED]
# ---------------------------------------------------------------------------
# Setup: 1 E core, 2 processes
#   P1: arrival=0, burst=2
#   P2: arrival=5, burst=3
#
# Trace:
#   t=0  : E0 activated (startup 0.1W, ONE TIME). P1 runs (t0~t2).
#   t=2~5: idle gap -> core stays warm, 0W consumed. No re-startup at t=5.
#   t=5  : P2 runs (t5~t8).
#
# Results:
#   P1: WT=0, TT=2, NTT=2/2=1.00
#   P2: WT=0, TT=3, NTT=3/3=1.00
#
# Power:
#   Startup: 0.1W  (t=0, once)
#   Running: (2 + 3)sec * 1W = 5.0W
#   Idle   : 3sec * 0W = 0.0W
#   Total  : 5.1W
#   (If wrongly re-starting: 0.1+0.1 + 5*1 = 5.2W -- this would be WRONG)
#
TC08 = TestCase(
    name="TC-08",
    description="Idle gap: core warm standby (0W idle, no re-startup) -- policy finalized",
    cores=CoreConfig(num_p_cores=0, num_e_cores=1),
    processes=make_procs([(1,0,2),(2,5,3)]),
    expected_gantt=[(1,"E0",0,2),(2,"E0",5,8)],
    expected_wt=[0, 0],
    expected_tt=[2, 3],
    expected_ntt=[1.00, 1.00],
    expected_power=5.1,
    notes=(
        "Policy 1 finalized: idle gap -> 0W, NO re-startup. "
        "Power = 0.1(startup) + 5(active sec)*1W = 5.1W. "
        "Wrong answer if re-startup charged: 5.2W."
    )
)

# ---------------------------------------------------------------------------
# TC-09  Stress: 15 processes, 4 cores (2P+2E) -- invariants only
# ---------------------------------------------------------------------------
TC09 = TestCase(
    name="TC-09",
    description="Stress: 15 processes on 4 cores (2P+2E) -- invariant assertions only",
    cores=CoreConfig(num_p_cores=2, num_e_cores=2),
    processes=make_procs([
        (1,0,3),(2,0,5),(3,1,2),(4,1,8),(5,2,1),
        (6,2,4),(7,3,6),(8,3,2),(9,4,7),(10,4,3),
        (11,5,1),(12,5,9),(13,6,4),(14,7,2),(15,8,5),
    ]),
    expected_gantt=[],
    expected_wt=[],
    expected_tt=[],
    expected_ntt=[],
    expected_power=-1,
    notes="Invariant checks only; hand-calculation not feasible at this scale."
)


# ===========================================================================
# PYTEST TEST FUNCTIONS
# ===========================================================================

ALL_CASES = [TC01, TC02, TC03, TC04, TC05, TC06, TC07, TC08]


def run_hrrn(tc: TestCase):
    try:
        from algorithms.hrrn import schedule as hrrn
        from models.sim_config import SimConfig
        from models.core_config import CoreConfig

        config = SimConfig(
            processes=tc.processes,
            core_config=tc.cores,
            algorithm="HRRN",
        )
        return hrrn(config)
    except ImportError:
        pytest.skip("algorithms.hrrn not yet implemented")


# ── Gantt ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tc", ALL_CASES, ids=[tc.name for tc in ALL_CASES])
def test_gantt(tc: TestCase):
    _, gantt = run_hrrn(tc)
    assert sorted(gantt) == sorted(tc.expected_gantt), (
        f"[{tc.name}] Gantt mismatch.\n"
        f"  Expected: {tc.expected_gantt}\n"
        f"  Got     : {gantt}"
    )


# ── Waiting time ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("tc", ALL_CASES, ids=[tc.name for tc in ALL_CASES])
def test_waiting_time(tc: TestCase):
    processes, _ = run_hrrn(tc)
    actual = [p.waiting_time for p in sorted(processes, key=lambda p: p.pid)]
    assert actual == tc.expected_wt, (
        f"[{tc.name}] WT mismatch.\n"
        f"  Expected: {tc.expected_wt}\n"
        f"  Got     : {actual}"
    )


# ── Turnaround time ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tc", ALL_CASES, ids=[tc.name for tc in ALL_CASES])
def test_turnaround_time(tc: TestCase):
    processes, _ = run_hrrn(tc)
    actual = [p.turnaround_time for p in sorted(processes, key=lambda p: p.pid)]
    assert actual == tc.expected_tt, (
        f"[{tc.name}] TT mismatch.\n"
        f"  Expected: {tc.expected_tt}\n"
        f"  Got     : {actual}"
    )


# ── NTT (tolerance +-0.01) -- denominator = logical burst_time ─────────────

@pytest.mark.parametrize("tc", ALL_CASES, ids=[tc.name for tc in ALL_CASES])
def test_ntt(tc: TestCase):
    processes, _ = run_hrrn(tc)
    for p, expected in zip(sorted(processes, key=lambda x: x.pid), tc.expected_ntt):
        assert abs(p.normalized_turnaround_time - expected) < 0.01, (
            f"[{tc.name}] NTT mismatch for P{p.pid}.\n"
            f"  Expected: {expected:.4f}  Got: {p.normalized_turnaround_time:.4f}\n"
            f"  NTT = TT / logical_burst_time (not actual_duration)"
        )


# ── Power (tolerance +-0.01 W) ─────────────────────────────────────────────

@pytest.mark.parametrize("tc", ALL_CASES, ids=[tc.name for tc in ALL_CASES])
def test_power(tc: TestCase):
    if tc.expected_power < 0:
        pytest.skip("Power check skipped for this test case")
    _, gantt = run_hrrn(tc)
    try:
        from algorithms.hrrn import calculate_power
        actual = calculate_power(gantt, tc.cores)
    except ImportError:
        pytest.skip("calculate_power not exported from algorithms.hrrn")
    assert abs(actual - tc.expected_power) < 0.01, (
        f"[{tc.name}] Power mismatch.\n"
        f"  Expected: {tc.expected_power:.2f}W  Got: {actual:.2f}W\n"
        f"  Policy: startup ONE-TIME per core; idle gap = 0W."
    )


# ── TC-09 stress invariants ────────────────────────────────────────────────

def test_tc09_invariants():
    processes, gantt = run_hrrn(TC09)
    assert len(processes) == 15, "Should complete all 15 processes"
    for p in processes:
        assert p.waiting_time >= 0,            f"P{p.pid}: negative WT"
        assert p.finish_time > p.arrival_time, f"P{p.pid}: finish <= arrival"
        assert p.turnaround_time == p.finish_time - p.arrival_time, \
            f"P{p.pid}: TT != finish - arrival"
        assert p.normalized_turnaround_time > 0, f"P{p.pid}: NTT <= 0"
        # NTT can be < 1.0 on P cores (processes 2 units/sec)
    assert len(gantt) >= 15


# ── Non-preemption ─────────────────────────────────────────────────────────

def test_no_preemption():
    """Each process must appear in exactly one contiguous Gantt block."""
    _, gantt = run_hrrn(TC02)
    pids = [entry[0] for entry in gantt]
    for pid in set(pids):
        count = pids.count(pid)
        assert count == 1, f"P{pid} has {count} Gantt entries -- preemption detected!"


# ── Starvation prevention ──────────────────────────────────────────────────

def test_starvation_prevention():
    """Every process must eventually finish."""
    processes, _ = run_hrrn(TC06)
    for p in processes:
        assert p.finish_time != -1, f"P{p.pid} never finished (starvation)"


# ── Policy 1: idle gap must NOT trigger re-startup ─────────────────────────

def test_idle_no_restart_cost():
    """TC-08: idle gap must NOT generate a second startup charge."""
    _, gantt = run_hrrn(TC08)
    try:
        from algorithms.hrrn import calculate_power
        power = calculate_power(gantt, TC08.cores)
    except ImportError:
        pytest.skip("calculate_power not available")
    # Wrong (re-startup): 0.1 + 0.1 + 5*1 = 5.2W
    # Correct (no re-startup): 0.1 + 5*1  = 5.1W
    assert abs(power - 5.1) < 0.01, (
        f"Re-startup cost detected in idle gap. "
        f"Expected 5.1W, got {power:.2f}W."
    )


# ── Policy 2: highest-ratio gets P core ───────────────────────────────────

def test_highest_ratio_gets_p_core():
    """TC-05: at each dispatch point, highest-ratio process must go to P core."""
    _, gantt = run_hrrn(TC05)
    p_core_pids = {pid for pid, core, s, e in gantt if core.startswith("P")}
    # t=0 tie -> lower PID -> P1 to P core
    assert 1 in p_core_pids, "P1 (lower PID at t=0 tie) should be on P core"
    # t=2 tie -> lower PID -> P3 to P core
    assert 3 in p_core_pids, "P3 (lower PID at t=2 tie) should be on P core"


# ── Policy 3: NTT denominator = logical burst_time ────────────────────────

def test_ntt_uses_logical_burst():
    """TC-04: NTT must use logical burst_time, not actual_duration."""
    processes, _ = run_hrrn(TC04)
    p1 = next(p for p in processes if p.pid == 1)
    # P1: burst=4, TT=2. Correct NTT = 2/4 = 0.50
    # Wrong (actual_duration): NTT = 2/2 = 1.00
    assert abs(p1.normalized_turnaround_time - 0.50) < 0.01, (
        f"NTT for P1 should be 0.50 (TT=2 / logical_burst=4). "
        f"Got {p1.normalized_turnaround_time:.4f}. "
        f"Are you dividing by actual_duration (2) instead of burst_time (4)?"
    )


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["pytest", __file__, "-v"]))
