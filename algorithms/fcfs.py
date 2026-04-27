# fcfs.py / spn.py / hrrn.py (비선점)
from models.process import Process
def schedule(processes: list[Process]) -> tuple[list[Process], list[tuple]]:
    # Gantt chart 데이터
    gantt = [("P1", 0, 3), ("P2", 3, 7), ...]
    # 반환
    return processes, gantt