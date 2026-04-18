class Process:
    def __init__(self, pid, arrival_time, burst_time, priority=0):
        self.pid = pid
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.remaining_time = burst_time   # SRTN용
        self.priority = priority           # 확장용

        # 알고리즘이 채워주는 결과값
        self.start_time = None
        self.finish_time = None
        self.waiting_time = None
        self.turnaround_time = None
        self.response_time = None