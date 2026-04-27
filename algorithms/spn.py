"""
algorithms/spn.py
───────────────────
SPN (Shortest Process Next) 스케줄링 알고리즘 구현

확정 정책:
  1. Non-preemptive scheduling : 프로세스가 할당되면 끝날 때까지 코어를 점유함.
  2. Scheduling criteria : Burst Time이 가장 작은 프로세스 우선. 동점 시 PID 오름차순.
  3. 코어 배정 : 우선순위가 높은 프로세스를 P core에 우선 배정.
  4. 전력/성능: P core(속도 2, 3W), E core(속도 1, 1W) 명세 준수.
"""

import math
import copy
from typing import Optional
from models.process import Process
from models.sim_config import SimConfig
from models.core_config import CoreConfig


# ── 내부 상태 표현 ─────────────────────────────────────────

class _CoreState:
    def __init__(self, core_id: str, core_type: str):
        self.core_id: str = core_id  # "P0", "E0", ...
        self.core_type: str = core_type  # "P" or "E"
        self.process: Optional[Process] = None  # 현재 실행 중인 프로세스
        self.start_tick: int = 0  # 현재 작업 시작 시각
        self.end_tick: int = 0  # 현재 작업 종료 예정 시각
        self.activated: bool = False  # 최초 활성화 여부 (시동 전력용)

    @property
    def is_idle(self) -> bool:
        return self.process is None


# ═════════════════════════════════════════════════════════
# 핵심 함수
# ═════════════════════════════════════════════════════════
def schedule(config: SimConfig):
    # ___
    # SPN schedule Simulate
    processes = copy.deepcopy(config.processes)
    core_config = config.core_config

    gantt: list[tuple] = []

    # ── 코어 상태 초기화 ──────────────────────────────────────────────────
    cores: list[_CoreState] = []
    for i in range(core_config.num_p_cores):
        cores.append(_CoreState(core_id=f"P{i}", core_type="P"))
    for i in range(core_config.num_e_cores):
        cores.append(_CoreState(core_id=f"E{i}", core_type="E"))

    # ── 시뮬레이션 루프 ───────────────────────────────────────────────────
    tick = 0
    completed = 0
    total_procs = len(processes)

    while completed < total_procs:
        # 1) 이번 tick에 완료된 프로세스 처리
        _finish_completed(tick, cores, processes, gantt)

        # 2) 현재 tick까지 도착했고, 대기 중인 프로세스 목록
        waiting = _get_waiting(tick, processes, cores)

        # 3) 빈 코어에 SPN 순서로 배정
        idle_cores = [c for c in cores if c.is_idle]
        if waiting and idle_cores:
            _assign(tick, waiting, idle_cores, core_config, processes)

        # 4) 완료 카운트 갱신
        completed = sum(1 for p in processes if p.finish_time is not None)

        # 5) 다음 이벤트 tick으로 이동
        if completed < total_procs:
            tick = _next_tick(tick, cores, processes)

    # ── 결과값 계산 ───────────────────────────────────────────────────────
    _compute_metrics(processes, gantt, core_config)

    # ── 전력 계산 ─────────────────────────────────────────────────────────
    power = calculate_power(gantt, core_config)

    return processes, gantt, power


# ══════════════════════════════════════════════════════════════════════════════
# helper function
# ══════════════════════════════════════════════════════════════════════════════

def _finish_completed(tick: int, cores: list[_CoreState], processes: list[Process], gantt: list[tuple]) -> None:
    for core in cores:
        if not core.is_idle and core.end_tick == tick:
            proc = core.process
            proc.finish_time = tick
            gantt.append((proc.pid, core.core_id, core.start_tick, tick))
            core.process = None


def _get_waiting(tick: int, processes: list[Process], cores: list[_CoreState]) -> list[Process]:
    running_pids = {c.process.pid for c in cores if not c.is_idle}
    return [
        p for p in processes
        if p.arrival_time <= tick
           and p.finish_time is None
           and p.pid not in running_pids
    ]


def _assign(tick: int, waiting: list[Process], idle_cores: list[_CoreState], core_config: CoreConfig,
            processes: list[Process]) -> None:
    # SPN 정책: Burst Time 가장 작은 프로세스를 먼저 처리 (동점 시 PID 순)
    sorted_waiting = sorted(waiting, key=lambda p: (p.burst_time, p.pid))
    # P 코어 우선 배정
    sorted_cores = sorted(idle_cores, key=lambda c: (0 if c.core_type == "P" else 1))

    for proc, core in zip(sorted_waiting, sorted_cores):
        duration = core_config.actual_duration(proc.burst_time, core.core_type)
        core.process = proc
        core.start_tick = tick
        core.end_tick = tick + duration
        core.activated = True
        if proc.start_time is None:
            proc.start_time = tick


def _next_tick(tick: int, cores: list[_CoreState], processes: list[Process]) -> int:
    candidates = []
    for core in cores:
        if not core.is_idle:
            candidates.append(core.end_tick)
    for p in processes:
        if p.finish_time is None and p.arrival_time > tick:
            candidates.append(p.arrival_time)

    if not candidates: return tick + 1
    return min(candidates)


def _compute_metrics(processes, gantt, core_config):
    # 각 프로세스가 어떤 코어에서 실행되었는지 확인 (비선점 -> 1개만 존재)
    core_map = {pid: core_id for pid, core_id, s, e in gantt}
    for p in processes:
        if p.pid in core_map:
            core_type = core_map[p.pid][0]  # "P" or "E"
            actual_duration = core_config.actual_duration(p.burst_time, core_type)
            p.turnaround_time = p.finish_time - p.arrival_time
            p.waiting_time = p.turnaround_time - actual_duration
            p.response_time = p.start_time - p.arrival_time
            p.normalized_turnaround_time = p.turnaround_time / p.burst_time


def calculate_power(gantt: list[tuple], core_config: CoreConfig) -> float:
    total = 0.0
    activated_cores = set()
    for pid, core_id, start, end in gantt:
        core_type = core_id[0]
        if core_id not in activated_cores:
            total += core_config.startup_power(core_type)
            activated_cores.add(core_id)
        total += core_config.running_power(core_type) * (end - start)
    return total
