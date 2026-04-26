def schedule(processes, core_list=None):
    if core_list is None:
        core_list = ["E"]

    usable_cores = [i for i, core in enumerate(core_list) if core != "OFF"]

    for p in processes:
        p.remaining_time = p.burst_time
        p.start_time = None
        p.finish_time = None
        p.waiting_time = None
        p.turnaround_time = None
        p.normalized_turnaround_time = None
        p.response_time = None

    gantt = []
    total_energy = 0.0

    if not usable_cores:
        print("사용 가능한 코어가 없습니다.")
        return processes, gantt, total_energy

    time = 0
    completed = 0
    n = len(processes)

    core_active = [False] * len(core_list)
    run_time = {p.pid: 0 for p in processes}
    last_gantt_index = {}

    while completed < n:
        available = [
            p for p in processes
            if p.arrival_time <= time and p.remaining_time > 0
        ]

        if not available:
            next_times = [
                p.arrival_time for p in processes
                if p.remaining_time > 0
            ]

            if not next_times:
                break

            core_active = [False] * len(core_list)
            time = min(next_times)
            continue

        assigned = []
        used_pids = set()

        for core_idx in usable_cores:
            candidates = [
                p for p in available
                if p.pid not in used_pids
            ]

            if not candidates:
                break

            selected = min(
                candidates,
                key=lambda x: (x.remaining_time, x.arrival_time, str(x.pid))
            )

            assigned.append((core_idx, selected))
            used_pids.add(selected.pid)

        active_now = [False] * len(core_list)

        for core_idx, p in assigned:
            core_type = core_list[core_idx]

            speed = 2 if core_type == "P" else 1
            power = 3.0 if core_type == "P" else 1.0
            startup = 0.5 if core_type == "P" else 0.1

            if not core_active[core_idx]:
                total_energy += startup

            total_energy += power
            active_now[core_idx] = True

            if p.start_time is None:
                p.start_time = time
                p.response_time = time - p.arrival_time

            core_label = f"{core_type}{core_idx}"

            if (
                core_idx in last_gantt_index
                and gantt[last_gantt_index[core_idx]]["pid"] == p.pid
                and gantt[last_gantt_index[core_idx]]["finish_time"] == time
            ):
                gantt[last_gantt_index[core_idx]]["finish_time"] = time + 1
            else:
                gantt.append({
                    "pid": p.pid,
                    "start_time": time,
                    "finish_time": time + 1,
                    "core": core_label
                })
                last_gantt_index[core_idx] = len(gantt) - 1

            p.remaining_time -= speed
            run_time[p.pid] += 1

            if p.remaining_time <= 0:
                p.remaining_time = 0
                p.finish_time = time + 1
                p.turnaround_time = p.finish_time - p.arrival_time
                p.waiting_time = p.turnaround_time - run_time[p.pid]

                if p.burst_time != 0:
                    p.normalized_turnaround_time = round(
                        p.turnaround_time / p.burst_time, 2
                    )
                else:
                    p.normalized_turnaround_time = 0

                completed += 1

        core_active = active_now
        time += 1

    total_energy = round(total_energy, 2)

    return processes, gantt, total_energy