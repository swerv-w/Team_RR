"""
algorithms/rr.py
────────────────
Round Robin 스케줄링 알고리즘 구현.

핵심 정책:
  1. Quantum 단위    : 물리 시간(tick).
  2. 코어 배정        : ready queue 앞쪽 → P core 우선.
  3. 동시 이벤트 순서: 새규 도착 → preempted 순으로 큐 뒤에 추가.
  4. Idle 처리       : 입력 없을 코어비 최초 1회. idle 구간 0W.
  5. NTT 분모        : 논리적 burst_time 사용.

반환 형식:
  processes : list[Process]
  gantt     : list[tuple]   → (pid, core_id, start, end)
  power     : float         → 총 소비전력 (W)
"""

import copy
import math
from collections import deque

from models.process import Process
from models.sim_config import SimConfig
from models.core_config import CoreConfig

# P/E 코어 속도 (unit/tick). 명세 고정값.
_CORE_SPEED: dict[str, int] = {"P": 2, "E": 1}


class _CoreState:
    """시뮬레이션 중 개별 코어의 상태를 추적하는 내부 클래스."""

    def __init__(self, core_id: str, core_type: str):
        self.core_id: str = core_id        # "P0", "E0", ...
        self.core_type: str = core_type    # "P" or "E"
        self.process: Process | None = None
        self.segment_start: int = 0
        self.quantum_end: int = 0
        self.will_finish: bool = False     # 이 quantum 안에 완료 여부
        self.activated: bool = False

    @property
    def is_idle(self) -> bool:
        return self.process is None


# ─────────────────────────────── public API ──────────────────────────────────

def schedule(config: SimConfig) -> tuple[list[Process], list[tuple], float]:
    """
    Round Robin 스케줄 계산.

    Parameters
    ----------
    config : SimConfig
        processes, core_config, time_quantum 포함.

    Returns
    -------
    processes : list[Process]
    gantt     : list[tuple]   → (pid, core_id, start, end)
    power     : float         → 총 소비전력 (W)
    """
    assert config.time_quantum is not None and config.time_quantum >= 1, \
        "time_quantum must be a positive integer"

    procs = copy.deepcopy(config.processes)
    cc = config.core_config
    tq = config.time_quantum

    # 도착 순으로 정렬한 대기 목록
    pending: deque[Process] = deque(sorted(procs, key=lambda p: p.arrival_time))

    # 코어 초기화: P 코어 우선 배치
    cores: list[_CoreState] = []
    for i in range(cc.num_p_cores):
        cores.append(_CoreState(f"P{i}", "P"))
    for i in range(cc.num_e_cores):
        cores.append(_CoreState(f"E{i}", "E"))

    p_cores = [c for c in cores if c.core_type == "P"]
    e_cores = [c for c in cores if c.core_type == "E"]

    ready: deque[Process] = deque()
    gantt: list[tuple] = []
    done = 0
    total = len(procs)
    tick = 0

    while done < total:
        # 1. quantum 만료/완료된 코어 처리
        preempted = _handle_finished(cores, tick, tq, gantt)
        done = sum(1 for p in procs if p.finish_time is not None)

        # 2. tick 시간에 도착한 프로세스 → ready queue
        _enqueue_arrivals(pending, ready, tick)

        # 3. preempted 프로세스 → ready queue 뒤
        for p in preempted:
            ready.append(p)

        # 4. idle 코어에 배정 (P 우선)
        _assign_to_idle(p_cores, e_cores, ready, tick, tq)

        if done == total:
            break

        # 5. 다음 이벤트 tick으로 이동
        next_tick = _next_event_tick(cores, pending)
        if next_tick is None:
            break  # 비정상 종료 방지
        tick = next_tick

    _compute_metrics(procs, gantt)
    power = calculate_power(gantt, cc)
    return procs, gantt, power


# ─────────────────────────────── helpers ─────────────────────────────────────

def _handle_finished(
    cores: list[_CoreState],
    tick: int,
    time_quantum: int,
    gantt: list[tuple],
) -> list[Process]:
    """
    tick 시간에 quantum이 만료된 코어를 처리한다.
    """
    preempted: list[Process] = []
    for core in cores:
        if core.is_idle or tick != core.quantum_end:
            continue

        proc = core.process
        gantt.append((proc.pid, core.core_id, core.segment_start, tick))

        if core.will_finish:
            proc.remaining_time = 0
            proc.finish_time = tick
        else:
            proc.remaining_time -= time_quantum * _CORE_SPEED[core.core_type]
            preempted.append(proc)

        core.process = None

    return preempted


def _enqueue_arrivals(
    pending: deque[Process],
    ready: deque[Process],
    tick: int,
) -> None:
    """pending에서 arrival_time == tick인 프로세스를 ready queue에 추가."""
    while pending and pending[0].arrival_time == tick:
        ready.append(pending.popleft())


def _assign_to_idle(
    p_cores: list[_CoreState],
    e_cores: list[_CoreState],
    ready: deque[Process],
    tick: int,
    time_quantum: int,
) -> None:
    """idle 코어에 ready queue 앞에서 꺼내 배정. P 코어 우선."""
    idle = [c for c in p_cores if c.is_idle] + [c for c in e_cores if c.is_idle]
    for core in idle:
        if not ready:
            break
        _assign(core, ready.popleft(), tick, time_quantum)


def _assign(
    core: _CoreState,
    proc: Process,
    tick: int,
    time_quantum: int,
) -> None:
    """코어에 프로세스를 배정하고 quantum 종료 시간을 계산한다."""
    speed = _CORE_SPEED[core.core_type]
    needed_ticks = math.ceil(proc.remaining_time / speed)
    actual_ticks = min(needed_ticks, time_quantum)

    core.process = proc
    core.segment_start = tick
    core.quantum_end = tick + actual_ticks
    core.will_finish = needed_ticks <= time_quantum

    if not core.activated:
        core.activated = True
    if proc.start_time is None:
        proc.start_time = tick


def _next_event_tick(
    cores: list[_CoreState],
    pending: deque[Process],
) -> int | None:
    """다음 이벤트(quantum 만료 또는 새규 도착) 시간을 반환."""
    candidates: list[int] = []
    for c in cores:
        if not c.is_idle:
            candidates.append(c.quantum_end)
    if pending:
        candidates.append(pending[0].arrival_time)
    return min(candidates) if candidates else None


def _compute_metrics(processes: list[Process], gantt: list[tuple]) -> None:
    """Gantt로부터 각 프로세스의 결과 지표를 계산한다."""
    cpu_ticks: dict = {}
    for pid, _core, start, end in gantt:
        cpu_ticks[pid] = cpu_ticks.get(pid, 0) + (end - start)

    for proc in processes:
        proc.turnaround_time = proc.finish_time - proc.arrival_time
        proc.waiting_time = proc.turnaround_time - cpu_ticks.get(proc.pid, 0)
        proc.response_time = proc.start_time - proc.arrival_time
        proc.normalized_turnaround_time = proc.turnaround_time / proc.burst_time


# ─────────────────────────────── power ───────────────────────────────────────

def calculate_power(gantt: list[tuple], core_config: CoreConfig) -> float:
    """
    총 소비전력(W) 계산.
    - 코어별 최초 활성화 시 startup_power 1회
    - 각 Gantt 세그먼트: running_power * (end - start)
    - idle 구간: 0 W
    """
    total = 0.0
    activated: set = set()
    for _pid, core_id, start, end in gantt:
        core_type = core_id[0]  # "P" or "E"
        if core_id not in activated:
            total += core_config.startup_power(core_type)
            activated.add(core_id)
        total += core_config.running_power(core_type) * (end - start)
    return total
