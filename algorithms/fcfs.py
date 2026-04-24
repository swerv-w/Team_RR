# fcfs.py / spn.py / hrrn.py (비선점)
#이벤트 기반 처리
def schedule(processes, core_list):
    processes.sort(key=lambda x: x.arrival_time) #도착시간 기준 정렬
    gantt = []
    total_energy = 0.0
    core_available_time = [0.0] * len(core_list)

    for p in processes:
        best_core_idx = -1 #best core 미선택
        earliest_time = float('inf') #earliest_time = 무한대로 설정

        for i in range(len(core_list)):
            if core_list[i] == 'OFF': continue #core를 아예 사용안함
            if core_available_time[i] < earliest_time:
                earliest_time = core_available_time[i]
                best_core_idx = i

        if best_core_idx == -1:
            print("사용 가능한 코어가 없습니다.")
            break
        
        #시작 시간: 코어 사용 가능한 시간, 도착 시간 비교
        start_time = max(earliest_time, p.arrival_time)

        #코어 성능(P/E)
        core_type = core_list[best_core_idx]
        speed = 2.0 if core_type == 'P' else 1.0
        power = 3.0 if core_type == 'P' else 1.0
        startup = 0.5 if core_type == 'P' else 0.1

        execution_time = p.burst_time / speed 
        finish_time = start_time + execution_time

        p.start_time = start_time
        p.finish_time = finish_time
        p.waiting_time = start_time - p.arrival_time
        p.turnaround_time = finish_time - p.arrival_time
        p.remaining_time = 0

        if start_time > earliest_time:
            total_energy += startup

        total_energy += (execution_time * power)
    # Gantt chart 데이터
        gantt.append({
            "pid": p.pid,
            "start_time": start_time,
            "finish_time": finish_time,
            "core": best_core_idx
        })
        core_available_time[best_core_idx] = finish_time
    total_energy = round(total_energy, 2)
    # 반환
    return processes, gantt, total_energy