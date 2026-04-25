"""
models/core_config.py
─────────────────────
코어 구성 및 시스템 스펙 상수를 정의하는 모델.

시스템 스펙 (확정):
  E core: 1 unit/sec, 동작 1W/sec, 시동 0.1W, idle 0W
  P core: 2 unit/sec, 동작 3W/sec, 시동 0.5W, idle 0W
  - 시동 전력: 코어 최초 활성화 시 1회만 발생
  - idle 전력: 0W (warm standby, 재시동 없음)
"""

from dataclasses import dataclass


@dataclass
class CoreConfig:
    num_p_cores: int = 0
    num_e_cores: int = 0

    # ── 성능 (units/sec) ──────────────────────────────────────────────────
    P_CORE_SPEED: int = 2
    E_CORE_SPEED: int = 1

    # ── 전력 (W) ──────────────────────────────────────────────────────────
    P_CORE_POWER  : float = 3.0   # 동작 전력 (W/sec)
    E_CORE_POWER  : float = 1.0   # 동작 전력 (W/sec)
    P_CORE_STARTUP: float = 0.5   # 시동 전력 (최초 1회)
    E_CORE_STARTUP: float = 0.1   # 시동 전력 (최초 1회)
    P_CORE_IDLE   : float = 0.0   # idle 전력 (정책: warm standby = 0W)
    E_CORE_IDLE   : float = 0.0   # idle 전력 (정책: warm standby = 0W)

    # ── 제약 (유효성 검사에서 사용) ───────────────────────────────────────
    MAX_CORES: int = 4

    @property
    def total_cores(self) -> int:
        return self.num_p_cores + self.num_e_cores

    def actual_duration(self, burst_time: int, core_type: str) -> int:
        """
        논리적 burst_time을 해당 코어에서의 실제 실행 시간(초)으로 변환.

        Parameters
        ----------
        burst_time : 논리적 작업량 (units)
        core_type  : "P" 또는 "E"

        Returns
        -------
        실제 실행 시간 (초) — ceiling 적용
        """
        import math
        speed = self.P_CORE_SPEED if core_type == "P" else self.E_CORE_SPEED
        return math.ceil(burst_time / speed)

    def running_power(self, core_type: str) -> float:
        """코어 타입에 따른 동작 전력 반환."""
        return self.P_CORE_POWER if core_type == "P" else self.E_CORE_POWER

    def startup_power(self, core_type: str) -> float:
        """코어 타입에 따른 시동 전력 반환 (최초 1회용)."""
        return self.P_CORE_STARTUP if core_type == "P" else self.E_CORE_STARTUP

    def __repr__(self) -> str:
        return (f"CoreConfig(P={self.num_p_cores}, E={self.num_e_cores}, "
                f"total={self.total_cores})")
