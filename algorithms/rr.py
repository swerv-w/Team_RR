# rr.py (선점 + time quantum)
def schedule(processes: list[Process], time_quantum: int) -> tuple[list[Process], list[tuple]]:
    # Gantt chart 데이터
    gantt = [("P1", 0, 3), ("P2", 3, 7), ...]

    # 반환
    return processes, gantt