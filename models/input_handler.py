"""
models/input_handler.py
────────────────────────
사용자 입력을 SimConfig로 변환하는 모듈.

구조:
  validate_*()   → 유효성 검사 로직 (CLI / PyQt5 공용)
  parse_inputs() → 값을 받아 SimConfig 생성 (CLI / PyQt5 공용)
  get_sim_config() → CLI 전용: input()으로 수집 후 parse_inputs() 호출

PyQt5 연동 시:
  UI 담당 팀원은 validate_*() 와 parse_inputs() 만 import해서 사용.
  get_sim_config() 는 건드리지 않아도 됨.
"""

from typing import Optional

from core_config import CoreConfig
from process import Process
from sim_config import SimConfig, ALGORITHMS


# ══════════════════════════════════════════════════════════════════════════════
# 유효성 검사 (CLI / PyQt5 공용)
# ══════════════════════════════════════════════════════════════════════════════

def validate_num_processes(n) -> Optional[str]:
    """
    프로세스 수 유효성 검사.

    Returns
    -------
    None    → 유효
    str     → 오류 메시지
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "정수를 입력해주세요."
    if not (1 <= n <= 15):
        return "프로세스 수는 1 이상 15 이하여야 합니다."
    return None


def validate_num_cores(total, num_p) -> Optional[str]:
    """
    코어 수 유효성 검사.

    Parameters
    ----------
    total : 전체 코어 수
    num_p : P코어 수
    """
    try:
        total, num_p = int(total), int(num_p)
    except (TypeError, ValueError):
        return "정수를 입력해주세요."
    if not (1 <= total <= 4):
        return "프로세서 수는 1 이상 4 이하여야 합니다."
    if not (0 <= num_p <= total):
        return f"P코어 수는 0 이상 {total} 이하여야 합니다."
    return None


def validate_arrival_times(values: list, n: int) -> Optional[str]:
    """
    도착시간 리스트 유효성 검사.

    Parameters
    ----------
    values : 입력된 도착시간 리스트 (int 또는 str 혼용 가능)
    n      : 기대하는 프로세스 수
    """
    if len(values) != n:
        return f"도착시간은 {n}개여야 합니다. (현재 {len(values)}개)"
    try:
        parsed = [int(v) for v in values]
    except (TypeError, ValueError):
        return "도착시간은 정수여야 합니다."
    if any(v < 0 for v in parsed):
        return "도착시간은 0 이상이어야 합니다."
    return None


def validate_burst_times(values: list, n: int) -> Optional[str]:
    """
    실행시간 리스트 유효성 검사.

    Parameters
    ----------
    values : 입력된 실행시간 리스트 (int 또는 str 혼용 가능)
    n      : 기대하는 프로세스 수
    """
    if len(values) != n:
        return f"실행시간은 {n}개여야 합니다. (현재 {len(values)}개)"
    try:
        parsed = [int(v) for v in values]
    except (TypeError, ValueError):
        return "실행시간은 정수여야 합니다."
    if any(v < 1 for v in parsed):
        return "실행시간은 1 이상이어야 합니다."
    return None


def validate_algorithm(algo: str) -> Optional[str]:
    """알고리즘 선택 유효성 검사."""
    if algo.upper() not in ALGORITHMS:
        return f"알고리즘은 {' / '.join(ALGORITHMS)} 중 하나여야 합니다."
    return None


def validate_time_quantum(tq) -> Optional[str]:
    """RR time quantum 유효성 검사."""
    try:
        tq = int(tq)
    except (TypeError, ValueError):
        return "Time quantum은 정수여야 합니다."
    if not (1 <= tq <= 100):
        return "Time quantum은 1 이상 100 이하여야 합니다."
    return None


# ══════════════════════════════════════════════════════════════════════════════
# SimConfig 생성 (CLI / PyQt5 공용)
# ══════════════════════════════════════════════════════════════════════════════

def parse_inputs(
    num_processes : int,
    num_p_cores   : int,
    num_e_cores   : int,
    arrival_times : list,
    burst_times   : list,
    algorithm     : str,
    time_quantum  : Optional[int] = None,
) -> SimConfig:
    """
    검증된 값을 받아 SimConfig를 생성한다.
    이 함수를 호출하기 전에 반드시 validate_*() 로 검증할 것.

    Parameters
    ----------
    num_processes : 프로세스 수
    num_p_cores   : P코어 수
    num_e_cores   : E코어 수
    arrival_times : 각 프로세스 도착시간 리스트 (pid 순서)
    burst_times   : 각 프로세스 실행시간 리스트 (pid 순서)
    algorithm     : 알고리즘 이름 (대소문자 무시)
    time_quantum  : RR 전용, 나머지 None

    Returns
    -------
    SimConfig
    """
    processes = [
        Process(
            pid=i + 1,
            arrival_time=int(arrival_times[i]),
            burst_time=int(burst_times[i]),
        )
        for i in range(num_processes)
    ]

    core_config = CoreConfig(
        num_p_cores=num_p_cores,
        num_e_cores=num_e_cores,
    )

    return SimConfig(
        processes=processes,
        core_config=core_config,
        algorithm=algorithm.upper(),
        time_quantum=int(time_quantum) if time_quantum is not None else None,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLI 전용
# ══════════════════════════════════════════════════════════════════════════════

def _cli_input_int(prompt: str, min_val: int, max_val: int) -> int:
    """유효한 정수를 입력받을 때까지 반복 (CLI 전용)."""
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"  ⚠  {min_val} 이상 {max_val} 이하의 정수를 입력해주세요.")


def _cli_input_int_list(prompt: str, count: int, min_val: int = 0) -> list[int]:
    """공백으로 구분된 정수 count개를 입력받을 때까지 반복 (CLI 전용)."""
    while True:
        raw = input(prompt).strip().split()
        try:
            vals = [int(r) for r in raw]
            if len(vals) == count and all(v >= min_val for v in vals):
                return vals
        except ValueError:
            pass
        print(f"  ⚠  {min_val} 이상의 정수 {count}개를 공백으로 구분하여 입력해주세요.")


def _cli_input_choice(prompt: str, choices: list[str]) -> str:
    """choices 중 하나를 선택받을 때까지 반복 (CLI 전용, 대소문자 무시)."""
    choices_upper = [c.upper() for c in choices]
    while True:
        raw = input(prompt).strip().upper()
        if raw in choices_upper:
            return raw
        print(f"  ⚠  {' / '.join(choices)} 중 하나를 입력해주세요.")


def get_sim_config() -> SimConfig:
    """
    CLI 전용: 터미널에서 단계별로 입력받아 SimConfig를 반환한다.
    PyQt5 UI에서는 이 함수를 사용하지 말 것.
    """
    print("\n" + "=" * 50)
    print("  CPU 스케줄링 시뮬레이터")
    print("=" * 50)

    # ── Step 1: 프로세스 수 ───────────────────────────────────────────────
    n = _cli_input_int("\n1. 프로세스는 몇 개입니까? (1~15): ", 1, 15)

    # ── Step 2: 프로세서 수 및 P/E 코어 구성 ─────────────────────────────
    total_cores = _cli_input_int("\n2. 프로세서는 몇 개입니까? (1~4): ", 1, 4)

    if total_cores == 1:
        core_type = _cli_input_choice(
            "   코어 타입을 선택하세요 (P / E): ", ["P", "E"]
        )
        num_p = 1 if core_type == "P" else 0
    else:
        num_p = _cli_input_int(
            f"   P코어는 몇 개입니까? (0~{total_cores}): ", 0, total_cores
        )
    num_e = total_cores - num_p
    print(f"   → P코어 {num_p}개, E코어 {num_e}개로 설정됩니다.")

    # ── Step 3: 도착시간 / 실행시간 ──────────────────────────────────────
    print(f"\n3. 프로세스 {n}개의 도착시간과 실행시간을 입력해주세요.")
    arrival_times = _cli_input_int_list(
        f"   도착시간 ({n}개, 공백 구분): ", n, min_val=0
    )
    burst_times = _cli_input_int_list(
        f"   실행시간 ({n}개, 공백 구분): ", n, min_val=1
    )

    # ── Step 4: 알고리즘 선택 ────────────────────────────────────────────
    print(f"\n4. 스케줄링 알고리즘을 선택해주세요.")
    print(f"   선택지: {' / '.join(ALGORITHMS)}")
    algorithm = _cli_input_choice("   알고리즘: ", ALGORITHMS)

    # ── Step 4-1: RR → time quantum ──────────────────────────────────────
    time_quantum = None
    if algorithm == "RR":
        time_quantum = _cli_input_int(
            "\n   4-1. Time Quantum을 입력해주세요 (1~100): ", 1, 100
        )

    # ── 확인 출력 ─────────────────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("  입력 확인")
    print("-" * 50)
    print(f"  프로세스 수   : {n}개")
    print(f"  코어 구성     : P코어 {num_p}개, E코어 {num_e}개")
    print(f"  알고리즘      : {algorithm}"
          + (f" (quantum={time_quantum})" if time_quantum else ""))
    print(f"  {'PID':<5} {'도착시간':<8} {'실행시간'}")
    for i in range(n):
        print(f"  {i+1:<5} {arrival_times[i]:<8} {burst_times[i]}")
    print("-" * 50 + "\n")

    return parse_inputs(
        num_processes=n,
        num_p_cores=num_p,
        num_e_cores=num_e,
        arrival_times=arrival_times,
        burst_times=burst_times,
        algorithm=algorithm,
        time_quantum=time_quantum,
    )


# ── 직접 실행 테스트 ───────────────────────────────────────────────────────
if __name__ == "__main__":
    config = get_sim_config()
    print("SimConfig 생성 완료:")
    print(f"  {config}")
    print(f"  프로세스: {config.processes}")
