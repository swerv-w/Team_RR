"""
algorithms/hrrn.py
───────────────────
HRRN (Highest Response Ratio Next) 스케줄링 알고리즘 구현.

확정 정책:
  1. Idle 전력  : 시동 전력 코어당 최초 1회. idle 구간 0W.
  2. 코어 배정  : Highest Response Ratio → P core 우선.
                  동점 시 PID 오름차순.
  3. NTT 분모   : 논리적 burst_time 사용.

반환 형식:
  processes : list[Process]  — 결과값이 채워진 프로세스 리스트
  gantt     : list[tuple]    — (pid, core_id, start, end)
  power     : float          — 총 소비전력 (W)
"""

import math
from typing import Optional
from models.process import Process
from models.sim_config import SimConfig
from models.core_config import CoreConfig


# ── 내부 상태 표현 ─────────────────────────────────────────────────────────

class _CoreState:
    """
    시뮬레이션 중 개별 코어의 상태를 추적하는 내부 클래스.
    hrrn() 함수 외부에서 직접 사용하지 않는다.
    """
    def __init__(self, core_id: str, core_type: str):
        self.core_id   : str             = core_id    # "P0", "E0", ...
        self.core_type : str             = core_type  # "P" or "E"
        self.process   : Optional[Process] = None     # 현재 실행 중인 프로세스
        self.start_tick: int             = 0          # 현재 작업 시작 시각
        self.end_tick  : int             = 0          # 현재 작업 종료 예정 시각
        self.activated : bool            = False      # 최초 활성화 여부 (시동 전력용)

    @property
    def is_idle(self) -> bool:
        return self.process is None

    def __repr__(self):
        return (f"_CoreState({self.core_id}, "
                f"{'idle' if self.is_idle else f'running P{self.process.pid}'})")


# ══════════════════════════════════════════════════════════════════════════════
# 핵심 함수
# ══════════════════════════════════════════════════════════════════════════════

def schedule(config: SimConfig):
    """
    HRRN 스케줄링을 시뮬레이션한다.

    Parameters
    ----------
    config : SimConfig
        .processes   — 입력 프로세스 리스트
        .core_config — 코어 구성 및 스펙

    Returns
    -------
    processes : list[Process]
        start_time, finish_time, waiting_time,
        turnaround_time, response_time 가 채워진 리스트.
    gantt : list[tuple]
        각 원소: (pid, core_id, start, end)
    power : float
        총 소비전력 (W)
    """
    import copy
    processes   = copy.deepcopy(config.processes)
    core_config = config.core_config

    gantt: list[tuple] = []

    # ── 코어 상태 초기화 ──────────────────────────────────────────────────
    cores: list[_CoreState] = []
    for i in range(core_config.num_p_cores):
        cores.append(_CoreState(core_id=f"P{i}", core_type="P"))
    for i in range(core_config.num_e_cores):
        cores.append(_CoreState(core_id=f"E{i}", core_type="E"))

    # ── 시뮬레이션 루프 ───────────────────────────────────────────────────
    tick        = 0
    completed   = 0
    total_procs = len(processes)

    while completed < total_procs:

        # 1) 이번 tick에 완료된 프로세스 처리
        _finish_completed(tick, cores, processes, gantt)

        # 2) 현재 tick까지 도착했고 아직 배정 안 된 프로세스 목록
        waiting = _get_waiting(tick, processes, cores)

        # 3) 빈 코어에 HRRN 순서로 배정
        idle_cores = [c for c in cores if c.is_idle]
        if waiting and idle_cores:
            _assign(tick, waiting, idle_cores, core_config, processes)

        # 4) 완료 카운트 갱신
        completed = sum(1 for p in processes if p.finish_time is not None)

        # 5) 다음 이벤트 tick으로 이동 (완료 안 됐으면)
        if completed < total_procs:
            tick = _next_tick(tick, cores, processes)

    # ── 결과값 계산 ───────────────────────────────────────────────────────
    _compute_metrics(processes)

    # ── 전력 계산 ─────────────────────────────────────────────────────────
    power = calculate_power(gantt, core_config)

    return processes, gantt, power


# ══════════════════════════════════════════════════════════════════════════════
# 내부 헬퍼 함수
# ══════════════════════════════════════════════════════════════════════════════

def _response_ratio(process: Process, current_tick: int) -> float:
    """
    현재 tick 기준 Response Ratio를 계산한다.
    HRRN 공식: (waiting_time + burst_time) / burst_time

    Parameters
    ----------
    process      : 대기 중인 프로세스
    current_tick : 현재 시각
    """
    waiting_time = current_tick - process.arrival_time
    return (waiting_time + process.burst_time) / process.burst_time


def _actual_duration(burst_time: int, core_type: str, core_config: CoreConfig) -> int:
    """
    논리적 burst_time을 해당 코어에서의 실제 실행 시간(초)으로 변환.
    P core: ceil(burst / 2),  E core: burst
    """

    return core_config.actual_duration(burst_time, core_type)


def _finish_completed(
    tick: int,
    cores: list[_CoreState],
    processes: list[Process],
    gantt: list[tuple],
) -> None:
    """
    end_tick == tick 인 코어의 프로세스를 완료 처리하고 Gantt에 기록한다.
    완료된 코어는 idle 상태로 전환한다.
    """
    for core in cores:
        if not core.is_idle and core.end_tick == tick:
            proc = core.process
            proc.finish_time = tick
            gantt.append((proc.pid, core.core_id, core.start_tick, tick))
            core.process = None


def _get_waiting(
    tick: int,
    processes: list[Process],
    cores: list[_CoreState],
) -> list[Process]:
    """
    현재 tick까지 도착했고, 완료되지 않았으며, 현재 어떤 코어에도
    배정되지 않은 프로세스 목록을 반환한다.
    """
  
    running_pids = {c.process.pid for c in cores if not c.is_idle}
    return [
        p for p in processes
        if p.arrival_time <= tick
        and p.finish_time is None
        and p.pid not in running_pids
    ]


def _sort_by_ratio(waiting: list[Process], tick: int) -> list[Process]:
    """
    대기 프로세스를 Response Ratio 내림차순으로 정렬한다.
    동점이면 PID 오름차순 (정책 2).
    """

    return sorted(
        waiting,
        key=lambda p: (-_response_ratio(p, tick), p.pid)
    )

def _assign(
    tick: int,
    waiting: list[Process],
    idle_cores: list[_CoreState],
    core_config: CoreConfig,
    processes: list[Process],
) -> None:
    """
    대기 프로세스를 HRRN 순서로 idle 코어에 배정한다.

    정책 2: highest-ratio → P core 우선.
    idle_cores는 P core가 E core보다 앞에 오도록 정렬되어 있어야 한다.
    """

    sorted_waiting  = _sort_by_ratio(waiting, tick)
    sorted_cores    = sorted(idle_cores, key=lambda c: (0 if c.core_type=="P" else 1))
    
    for proc, core in zip(sorted_waiting, sorted_cores):
        duration        = _actual_duration(proc.burst_time, core.core_type, core_config)
        core.process    = proc
        core.start_tick = tick
        core.end_tick   = tick + duration
        core.activated  = True
    
        if proc.start_time is None:
            proc.start_time = tick


def _next_tick(
    tick: int,
    cores: list[_CoreState],
    processes: list[Process],
) -> int:
    """
    다음으로 이벤트가 발생하는 tick을 반환한다.
    이벤트: 코어 완료 시각 또는 미도착 프로세스의 arrival_time 중 가장 이른 것.
    """
    
    candidates = []
    for core in cores:
        if not core.is_idle:
            candidates.append(core.end_tick)
    for p in processes:
        if p.finish_time is None and p.arrival_time > tick:
            candidates.append(p.arrival_time)
    return min(candidates)


def _compute_metrics(processes: list[Process]) -> None:
    """
    모든 프로세스의 결과값을 계산해 채운다.
      waiting_time         = finish_time - arrival_time - burst_time
      turnaround_time      = finish_time - arrival_time
      response_time        = start_time  - arrival_time
      normalized_turnaround_time = turnaround_time / burst_time  (정책 3)
    """

    for p in processes:
        p.turnaround_time = p.finish_time - p.arrival_time
        p.waiting_time    = p.turnaround_time - p.burst_time
        p.response_time   = p.start_time - p.arrival_time
        p.normalized_turnaround_time = p.turnaround_time / p.burst_time



# ══════════════════════════════════════════════════════════════════════════════
# 전력 계산 (독립 함수 — 테스트에서 직접 호출 가능)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_power(gantt: list[tuple], core_config: CoreConfig) -> float:
    """
    Gantt 결과를 바탕으로 총 소비전력을 계산한다.

    정책 1:
      - 시동 전력: 코어가 처음 사용될 때 1회만 발생
      - idle 구간: 0W (재시동 없음)
      - 동작 전력: 실제 실행 시간(초) x 해당 코어 W/sec

    Parameters
    ----------
    gantt       : [(pid, core_id, start, end), ...]
    core_config : CoreConfig

    Returns
    -------
    총 소비전력 (W)
    """

    total = 0.0
    activated_cores = set()

    for pid, core_id, start, end in gantt:
        core_type = core_id[0]   # core_id => P0, P1 ... or E0, E1 ...
        duration  = end - start
    
        # 시동 전력 (최초 1회)
        if core_id not in activated_cores:
            total += core_config.startup_power(core_type)
            activated_cores.add(core_id)
    
        # 동작 전력
        total += core_config.running_power(core_type) * duration

    return total
