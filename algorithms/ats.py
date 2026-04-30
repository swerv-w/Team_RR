"""
algorithms/ats.py
───────────────────
[ 자작 알고리즘 ]
ATS (Average Time Service) 스케줄링 알고리즘 구현
- 정성현 (문제 있을시 연락 부탁드립니다.)

확정 정책:
  1. Preemptive scheduling : 프로세스가 할당되어도 코어 점유를 뺏길 수 있음.
  2. Scheduling criteria :
        - 프로세스들의 Burst Time의 평균(Average)을 계산
        - Time Quantum = BT의 평균을 기준
        - 실행중인 프로세스가 Time Quantum을 넘는다면? -> 자원 반납 진행
  3. 코어 배정 : 우선순위가 높은 프로세스를 P core에 우선 배정.
  4. 전력/성능: P core(속도 2, 3W), E core(속도 1, 1W) 명세 준수.

장점 :
  1. time quantum이 낮은 Round Robin에 비해 Context Switching 문제가 적다.
  2. 일반적인 표본에 대해 Round Robin보다 NTT값이 낮다. (유리하다)
  3. 기아현상(starvation) 예방, deadlock recovery가 동시에 된다는 점에서 SPN, SRTN, HRRN보다 유리하다.

문제점 :
  1. 평균의 함정 (BT의 평균만으로 time quantum을 결정시 Worst case 발생)
    - 만약, P(BT)에서 P1(100), P2(100), P3(100), P4(100), P5(1)의 경우,
      BT의 average값은 80.2이며 이 경우 "P5의 NTT값이 극단적으로 높아진다."
  2. BT 측정 기술이 요구되는데에 반해 SPN, SRTN, HRRN보다 대체적으로 NTT값이 높다.

개선방안 :
  1. time quantum 계산 기준 변경
    - BT의 평균값에 /2 또는 /3 를 진행 -> Worst case에서의 문제가 대폭 줄어든다.
    - 나누는 값이 증가할수록 Worst case 문제가 줄어들지만 지나치게 줄이면 RR과 차이가 없어진다. -> 선정 기준을 어떻게 할 것인가?
  2. 단순 평균이 아닌, '중앙값, 편차, 분산, 표준편차' 등을 활용한 새로운 time quantum 계산식을 세운다
    - 정확한 계산식의 성립이 어려움
    - 계산식이 복잡해질수록 Overhead 문제 발생

생각해볼 점 :
  1. 다중 코어 시스템에서 추가 개선점이 있는가?
  2. 프로세스 처리 도중에 새로운 프로세스의 자원 요청이 들어오면 time quantum을 수정해야할까?
  3. models/process.py에 self.average_burst_time 변수 추가?
"""

import math
import copy
from collections import deque
from typing import Optional, List, Tuple

from models.process import Process
from models.sim_config import SimConfig
from models.core_config import CoreConfig

# 코어별 물리적 처리 속도 (unit/sec)
_CORE_SPEED = {"P": 2, "E": 1}


class _CoreState:
    """시뮬레이션 중 개별 코어의 상태를 추적하는 내부 클래스."""

    def __init__(self, core_id: str, core_type: str):
        self.core_id: str = core_id  # "P0", "E0", ...
        self.core_type: str = core_type  # "P" or "E"
        self.process: Optional[Process] = None
        self.segment_start: int = 0
        self.quantum_end: int = 0  # 현재 할당된 퀀텀이 끝나는 절대 tick
        self.will_finish: bool = False  # 퀀텀 내에 작업이 완료되는지 여부
        self.activated: bool = False  # 시동 전력 계산용

    @property
    def is_idle(self) -> bool:
        return self.process is None


def schedule(config: SimConfig) -> Tuple[List[Process], List[Tuple], float]:
    # ATS 스케줄링 시뮬레이션 실행.

    # 1. 초기 설정 및 데이터 복사
    procs = copy.deepcopy(config.processes)
    cc = config.core_config

    if not procs:
        return [], [], 0.0

    # 2. ATS 핵심: Time Quantum 계산
    avg_bt = sum(p.burst_time for p in procs) / len(procs)
    if len(procs) < 4:
        tq = math.ceil(avg_bt / 2) # 프로세스의 갯수가 4개 미만일 땐 /2 를 사용한다.
    else:
        multiplier_bt = len(procs).bit_length()
        tq = math.ceil(avg_bt / multiplier_bt)
        # 프로세스의 갯수가 4개 이상일 땐 bit_length()를 활용한다.
        # /3 /4 ...으로 증가하나 이는 로그 함수와 같이 완만한 형태로 증가한다.

    # 프로세스 대기 목록 (도착 시간 순)
    pending = deque(sorted(procs, key=lambda p: p.arrival_time))

    # 3. 코어 초기화 (P코어 우선 리스트 구성)
    cores: List[_CoreState] = []
    for i in range(cc.num_p_cores):
        cores.append(_CoreState(f"P{i}", "P"))
    for i in range(cc.num_e_cores):
        cores.append(_CoreState(f"E{i}", "E"))

    p_cores = [c for c in cores if c.core_type == "P"]
    e_cores = [c for c in cores if c.core_type == "E"]

    ready_queue: deque[Process] = deque()
    gantt: List[Tuple] = []
    done_count = 0
    total_count = len(procs)
    tick = 0

    # 4. 시뮬레이션 루프
    while done_count < total_count:
        # Step A: 현재 tick에 만료(완료 또는 퀀텀 종료)된 코어 처리
        preempted_procs = _handle_finished_and_preemption(cores, tick, tq, gantt)

        # 완료된 프로세스 수 업데이트
        done_count = sum(1 for p in procs if p.finish_time is not None)

        # Step B: 현재 tick에 새로 도착한 프로세스 큐 삽입
        while pending and pending[0].arrival_time <= tick:
            ready_queue.append(pending.popleft())

        # Step C: 선점된(Quantum 초과) 프로세스를 큐 뒤에 삽입
        for p in preempted_procs:
            ready_queue.append(p)

        # Step D: 비어있는 코어에 프로세스 배정 (P코어 우선)
        _assign_to_idle_cores(p_cores, e_cores, ready_queue, tick, tq)

        if done_count == total_count:
            break

        # Step E: 다음 이벤트 tick 계산
        next_event = _get_next_tick(cores, pending, tick)
        if next_event is None: break
        tick = next_event

    # 5. 지표 계산 및 전력 소모량 합산
    _compute_final_metrics(procs, gantt)
    power = calculate_power(gantt, cc)

    return procs, gantt, power


def _handle_finished_and_preemption(cores: List[_CoreState], tick: int, tq: int, gantt: List[Tuple]) -> List[Process]:
    """완료되거나 Time Quantum을 다 쓴 프로세스를 처리."""
    preempted = []
    for core in cores:
        if core.is_idle or tick < core.quantum_end:
            continue

        proc = core.process
        # 간트 차트 기록: (pid, core_id, start, end)
        gantt.append((proc.pid, core.core_id, core.segment_start, tick))

        if core.will_finish:
            proc.remaining_time = 0
            proc.finish_time = tick
        else:
            # 소비된 작업량 차감 (실행 시간 * 코어 속도)
            work_done = (tick - core.segment_start) * _CORE_SPEED[core.core_type]
            proc.remaining_time -= work_done
            preempted.append(proc)

        core.process = None
    return preempted


def _assign_to_idle_cores(p_cores, e_cores, ready_queue, tick, tq):
    """쉬고 있는 코어에 P코어부터 우선적으로 배정."""
    # P -> E 순서로 빈 코어 탐색
    all_idle = [c for c in p_cores if c.is_idle] + [c for c in e_cores if c.is_idle]

    for core in all_idle:
        if not ready_queue:
            break

        proc = ready_queue.popleft()
        speed = _CORE_SPEED[core.core_type]

        # 실제 완료까지 필요한 시간 vs Time Quantum
        needed_ticks = math.ceil(proc.remaining_time / speed)
        run_ticks = min(needed_ticks, tq)

        core.process = proc
        core.segment_start = tick
        core.quantum_end = tick + run_ticks
        core.will_finish = (needed_ticks <= tq)
        core.activated = True

        if proc.start_time is None:
            proc.start_time = tick


def _get_next_tick(cores: List[_CoreState], pending: deque, current_tick: int) -> Optional[int]:
    """다음 이벤트가 발생하는 가장 빠른 tick을 반환."""
    candidates = []
    for c in cores:
        if not c.is_idle:
            candidates.append(c.quantum_end)
    if pending:
        candidates.append(pending[0].arrival_time)

    # 현재 tick보다 큰 값 중 가장 작은 값 선택
    future_events = [t for t in candidates if t > current_tick]
    return min(future_events) if future_events else current_tick + 1


def _compute_final_metrics(processes: List[Process], gantt: List[Tuple]):
    """각 프로세스의 반환시간, 대기시간 등 최종 지표 계산."""
    # 프로세스별 실제 CPU 사용 시간 합산
    cpu_usage = {}
    for pid, _, start, end in gantt:
        cpu_usage[pid] = cpu_usage.get(pid, 0) + (end - start)

    for p in processes:
        if p.finish_time is not None:
            p.turnaround_time = p.finish_time - p.arrival_time
            # 대기시간 = 반환시간 - 실제 실행에 걸린 tick 수 (코어 속도 반영된 결과)
            p.waiting_time = p.turnaround_time - cpu_usage.get(p.pid, 0)
            p.response_time = p.start_time - p.arrival_time
            # 정규화 반환시간 = 반환시간 / 초기 Burst Time
            p.normalized_turnaround_time = p.turnaround_time / p.burst_time


def calculate_power(gantt: List[Tuple], core_config: CoreConfig) -> float:
    """총 소비전력(W) 계산 (시동 전력 1회 + 동작 전력)."""
    total = 0.0
    activated_cores = set()
    for _, core_id, start, end in gantt:
        core_type = core_id[0]  # "P" or "E"
        if core_id not in activated_cores:
            total += core_config.startup_power(core_type)
            activated_cores.add(core_id)
        total += core_config.running_power(core_type) * (end - start)
    return total
