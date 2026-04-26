# srtn.py (선점)
class Process:
    def __init__(self, pid, arrival_time, burst_time):
        self.pid = pid
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.remaining_time = burst_time
        self.start_time = None
        self.finish_time = 0
        self.waiting_time = 0
        self.turnaround_time = 0

def schedule(processes: list[Process]) -> tuple[list[Process], list[tuple]]:
    time = 0.0
    completed = 0
    n = len(processes)

    processes.sort(key=lambda x: x.arrival_time)

    gantt = []
    current = None
    start_time = 0.0

    while completed < n:
        available = [p for p in processes if p.arrival_time <= time and p.remaining_time > 0]

        if not available:
            next_arrival = min(p.arrival_time for p in processes if p.remaining_time > 0)
            time = next_arrival
            continue

        selected = min(available, key=lambda x: x.remaining_time)

        if current != selected:
            if current is not None:
                gantt.append((current.pid, start_time, time))
            current = selected
            start_time = time
            if current.start_time is None:
                current.start_time = time

        next_arrivals = [p.arrival_time for p in processes if p.arrival_time > time and p.remaining_time > 0]
        next_arrival_time = min(next_arrivals) if next_arrivals else float('inf')

        run_time = min(selected.remaining_time, next_arrival_time - time)

        if run_time <= 0:
            time = next_arrival_time
            continue

        selected.remaining_time -= run_time
        time += run_time

        if selected.remaining_time == 0:
            selected.finish_time = time
            selected.turnaround_time = selected.finish_time - selected.arrival_time
            selected.waiting_time = selected.turnaround_time - selected.burst_time
            completed += 1

    if current is not None:
        gantt.append((current.pid, start_time, time))

    return processes, gantt

