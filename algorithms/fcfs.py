"""
algorithms/fcfs.py
───────────────────
FCFS (First-Come-First-Served) 스케줄링 알고리즘
- 이벤트 기반

핵심 정책:
  1. Idle 전력  : 시동 전력 코어당 최초 1회. idle 구간 0W.
  2. 코어 배정  : 도착 시간(arrival_time)이 빠른 순으로 배정. 
                  동점 시 PID 오름차순. idle 코어 중 P core 우선 배정.
  3. 진행 방식  : 비선점형(Non-preemptive). 프로세스에 코어를 할당 -> 종료될 때까지 사용
  4. 시간 처리  : 이벤트 기반. 코어 가용 시간(available_time)을 사용.
  5. NTT 분모   : 논리적 burst_time 사용.

반환 형식:
  processes : list[Process]  — 결과값이 채워진 프로세스 리스트
  gantt     : list[tuple]    — (pid, core_id, start, end)
  power     : float          — 총 소비전력 (W)
"""

import copy
from models.process import Process
from models.sim_config import SimConfig

class _CoreState:
    #코어 class 개설, 통일. 
    def __init__(self, core_id: str, core_type: str):
        self.core_id: str = core_id        # "P0", "E0", ...
        self.core_type: str = core_type    # "P" or "E"
        self.available_time: int = 0       # 코어가 비게 되는 시간
        self.activated: bool = False       # 시동 전력 최초 활성화 (최초 1회만)

    def __repr__(self): #core state 출력
        return f"_CoreState({self.core_id}, available_at={self.available_time})"


#FCFS 구현
def schedule(config: SimConfig):
    processes = copy.deepcopy(config.processes)
    #프로세스: 도착 시간 기준 정렬 (동점 시 PID 오름차순)
    processes.sort(key=lambda p: (p.arrival_time, p.pid))
    
    gantt: list[tuple] = []
    total_energy = 0.0
    
    # 코어 초기화(객체 리스트로 생성)
    cores: list[_CoreState] = []
    for i in range(config.core_config.num_p_cores):
        cores.append(_CoreState(core_id=f"P{i}", core_type="P"))
    for i in range(config.core_config.num_e_cores):
        cores.append(_CoreState(core_id=f"E{i}", core_type="E"))

    if not cores:
        return processes, gantt, total_energy

    #이벤트 기반 프로세스 배정
    for p in processes:
        
        #가장 먼저 끝나는(available_time이 가장 작은) 코어 탐색
        #동점일 경우 리스트 앞쪽에 있는 P코어가 우선 배정
        best_core = min(cores, key=lambda c: c.available_time)

        #시작 시간: 코어 사용 가능한 시간, 도착 시간 비교
        start_time = int(max(best_core.available_time, p.arrival_time))
        
        #실제 실행 시간
        execution_time = int(config.core_config.actual_duration(p.burst_time, best_core.core_type))
        finish_time = start_time + execution_time

        #프로세스 객체에 결과 기록
        p.start_time = start_time
        p.finish_time = finish_time
        p.turnaround_time = finish_time - p.arrival_time
        p.waiting_time = p.turnaround_time - execution_time
        p.response_time = start_time - p.arrival_time
        p.normalized_turnaround_time = p.turnaround_time / p.burst_time
        p.remaining_time = 0

        #소비 전력 계산
        if not best_core.activated:
            total_energy += config.core_config.startup_power(best_core.core_type)
            best_core.activated = True
            
        total_energy += config.core_config.running_power(best_core.core_type) * execution_time

        #간트 차트 기록 및 코어 업데이트
        gantt.append((p.pid, best_core.core_id, start_time, finish_time))
        best_core.available_time = finish_time

    return processes, gantt, round(total_energy, 2)