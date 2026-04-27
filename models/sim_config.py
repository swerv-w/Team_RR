"""
models/sim_config.py
─────────────────────
알고리즘 함수에 전달되는 시뮬레이션 설정 전체를 담는 모델.

사용 예시:
    from models.sim_config import SimConfig, ALGORITHMS
    from models.core_config import CoreConfig
    from models.process import Process

    config = SimConfig(
        processes=[Process(1, 0, 5), Process(2, 2, 3)],
        core_config=CoreConfig(num_p_cores=1, num_e_cores=1),
        algorithm="HRRN",
    )
"""

from dataclasses import dataclass, field
from typing import Optional, List

# 순환 import 방지: 타입 힌트용으로만 사용
from models.core_config import CoreConfig


ALGORITHMS = ["FCFS", "RR", "SPN", "SRTN", "HRRN"]


@dataclass
class SimConfig:
    processes   : List        # list[Process] — process.py 순환 import 방지로 List 사용
    core_config : CoreConfig
    algorithm   : str         # ALGORITHMS 중 하나
    time_quantum: Optional[int] = None  # RR 전용, 나머지는 None

    def __post_init__(self):
        """생성 시 기본 유효성 검사."""
        if self.algorithm not in ALGORITHMS:
            raise ValueError(
                f"algorithm은 {ALGORITHMS} 중 하나여야 합니다. 입력값: '{self.algorithm}'"
            )
        if self.algorithm == "RR" and self.time_quantum is None:
            raise ValueError("RR 알고리즘은 time_quantum이 필요합니다.")
        if self.algorithm != "RR" and self.time_quantum is not None:
            raise ValueError("time_quantum은 RR 알고리즘에서만 사용됩니다.")

    @property
    def num_processes(self) -> int:
        return len(self.processes)

    def __repr__(self) -> str:
        tq = f", quantum={self.time_quantum}" if self.time_quantum else ""
        return (f"SimConfig(algo={self.algorithm}{tq}, "
                f"procs={self.num_processes}, {self.core_config})")
