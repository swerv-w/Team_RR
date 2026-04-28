"""
ui/main_window.py
──────────────────
CPU 스케줄링 시뮬레이터 메인 UI.

구조:
  MainWindow
    ├── InputWidget   입력 영역 (프로세스 수, 코어 구성, 알고리즘, 도착/실행시간)
    └── OutputWidget  출력 영역 (Gantt 차트, 결과 테이블, 소비전력)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QScrollArea,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont

from models.input_handler import (
    parse_inputs,
    validate_num_processes,
    validate_num_cores,
    validate_arrival_times,
    validate_burst_times,
    validate_algorithm,
    validate_time_quantum,
)
from algorithms.fcfs import schedule as fcfs
from algorithms.rr import schedule as rr
from algorithms.spn import schedule as spn
from algorithms.srtn import schedule as srtn
from algorithms.hrrn import schedule as hrrn


# ══════════════════════════════════════════════════════════════════════════════
# Gantt 차트 위젯 (커스텀 위젯)
# ══════════════════════════════════════════════════════════════════════════════

class GanttWidget(QWidget):
    """
    Gantt 차트를 그려주는 커스텀 위젯.
    gantt: list[tuple] — (pid, core_id, start, end)
    """

    # 코어별 색상 (최대 4코어)
    COLORS = [
        QColor("#4A90D9"),   # P0 — 파랑
        QColor("#E67E22"),   # P1 — 주황
        QColor("#2ECC71"),   # E0 — 초록
        QColor("#9B59B6"),   # E1 — 보라
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gantt      = []
        self.core_ids   = []   # 코어 순서 (y축)
        self.max_time   = 0
        self.setMinimumHeight(150)

    def set_data(self, gantt: list):
        """Gantt 데이터를 설정하고 다시 그린다."""
        self.gantt    = gantt
        self.core_ids = sorted(set(core_id for _, core_id, _, _ in gantt))
        self.max_time = max(end for _, _, _, end in gantt) if gantt else 0
        self.update()   # paintEvent 트리거

    def paintEvent(self, event):
        """Qt가 자동 호출 — 위젯을 다시 그릴 때 실행된다."""
        if not self.gantt:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # ── 레이아웃 상수 ──────────────────────────────────────────────────
        MARGIN_LEFT  = 60    # 코어 이름 영역
        MARGIN_TOP   = 20
        MARGIN_BOTTOM= 30    # 시간축 영역
        ROW_HEIGHT   = 40
        ROW_GAP      = 10

        w = self.width()
        h = self.height()
        chart_w = w - MARGIN_LEFT - 20
        chart_h = h - MARGIN_TOP - MARGIN_BOTTOM

        if self.max_time == 0:
            return

        scale = chart_w / self.max_time   # 1tick당 픽셀 수

        # ── 코어별 행 그리기 ───────────────────────────────────────────────
        core_color_map = {
            core_id: self.COLORS[i % len(self.COLORS)]
            for i, core_id in enumerate(self.core_ids)
        }

        for row_idx, core_id in enumerate(self.core_ids):
            y = MARGIN_TOP + row_idx * (ROW_HEIGHT + ROW_GAP)

            # 코어 이름 (왼쪽)
            painter.setPen(Qt.black)
            painter.drawText(0, y, MARGIN_LEFT - 5, ROW_HEIGHT,
                             Qt.AlignRight | Qt.AlignVCenter, core_id)

            # 이 코어의 Gantt 블록들
            for pid, cid, start, end in self.gantt:
                if cid != core_id:
                    continue

                x = MARGIN_LEFT + int(start * scale)
                bw = max(int((end - start) * scale) - 2, 1)

                # 블록 배경
                color = core_color_map[core_id]
                painter.fillRect(x, y, bw, ROW_HEIGHT, color)

                # 블록 테두리
                painter.setPen(Qt.white)
                painter.drawRect(x, y, bw, ROW_HEIGHT)

                # PID 텍스트
                painter.setPen(Qt.white)
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(x, y, bw, ROW_HEIGHT,
                                 Qt.AlignCenter, f"P{pid}")

        # ── 시간축 ────────────────────────────────────────────────────────
        painter.setPen(Qt.black)
        painter.setFont(QFont("Arial", 8))
        axis_y = MARGIN_TOP + len(self.core_ids) * (ROW_HEIGHT + ROW_GAP)

        for t in range(self.max_time + 1):
            x = MARGIN_LEFT + int(t * scale)
            painter.drawLine(x, axis_y, x, axis_y + 5)
            painter.drawText(x - 5, axis_y + 6, 20, 15,
                             Qt.AlignCenter, str(t))

        painter.end()


# ══════════════════════════════════════════════════════════════════════════════
# 입력 위젯
# ══════════════════════════════════════════════════════════════════════════════

class InputWidget(QGroupBox):
    """프로세스/코어/알고리즘 입력 영역."""

    def __init__(self, parent=None):
        super().__init__("입력", parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # ── 행 1: 프로세스 수 / 코어 구성 ─────────────────────────────────
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("프로세스 수 (1~15):"))
        self.spin_proc = QSpinBox()
        self.spin_proc.setRange(1, 15)
        self.spin_proc.setValue(3)
        self.spin_proc.valueChanged.connect(self._on_proc_count_changed)
        row1.addWidget(self.spin_proc)

        row1.addSpacing(20)

        row1.addWidget(QLabel("P코어 수:"))
        self.spin_p = QSpinBox()
        self.spin_p.setRange(0, 4)
        self.spin_p.setValue(0)
        row1.addWidget(self.spin_p)

        row1.addWidget(QLabel("E코어 수:"))
        self.spin_e = QSpinBox()
        self.spin_e.setRange(0, 4)
        self.spin_e.setValue(1)
        row1.addWidget(self.spin_e)

        row1.addStretch()
        layout.addLayout(row1)

        # ── 행 2: 알고리즘 / Time Quantum ──────────────────────────────────
        row2 = QHBoxLayout()

        row2.addWidget(QLabel("알고리즘:"))
        self.combo_algo = QComboBox()
        self.combo_algo.addItems(["FCFS", "RR", "SPN", "SRTN", "HRRN"])
        self.combo_algo.currentTextChanged.connect(self._on_algo_changed)
        row2.addWidget(self.combo_algo)

        self.lbl_tq = QLabel("Time Quantum:")
        self.spin_tq = QSpinBox()
        self.spin_tq.setRange(1, 100)
        self.spin_tq.setValue(3)
        self.lbl_tq.setVisible(False)
        self.spin_tq.setVisible(False)
        row2.addWidget(self.lbl_tq)
        row2.addWidget(self.spin_tq)

        row2.addStretch()
        layout.addLayout(row2)

        # ── 행 3: 도착/실행시간 입력 테이블 ───────────────────────────────
        layout.addWidget(QLabel("프로세스별 도착시간 / 실행시간:"))
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["PID", "도착시간", "실행시간"])
        self.table.setFixedHeight(160)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # ── 행 4: 실행 버튼 ────────────────────────────────────────────────
        self.btn_run = QPushButton("▶  시뮬레이션 실행")
        self.btn_run.setFixedHeight(40)
        layout.addWidget(self.btn_run)

        self.setLayout(layout)
        self._on_proc_count_changed(self.spin_proc.value())

    def _on_proc_count_changed(self, n: int):
        """프로세스 수가 바뀌면 테이블 행 수를 맞춘다."""
        self.table.setRowCount(n)
        for i in range(n):
            # PID 열 (읽기 전용)
            pid_item = QTableWidgetItem(str(i + 1))
            pid_item.setFlags(Qt.ItemIsEnabled)   # 편집 불가
            self.table.setItem(i, 0, pid_item)

            # 도착시간 / 실행시간 기본값
            if self.table.item(i, 1) is None:
                self.table.setItem(i, 1, QTableWidgetItem("0"))
            if self.table.item(i, 2) is None:
                self.table.setItem(i, 2, QTableWidgetItem("1"))

    def _on_algo_changed(self, algo: str):
        """RR 선택 시 Time Quantum 입력 필드 표시."""
        is_rr = algo == "RR"
        self.lbl_tq.setVisible(is_rr)
        self.spin_tq.setVisible(is_rr)

    def get_inputs(self) -> dict:
        """
        현재 입력값을 딕셔너리로 반환한다.
        validate_*() 는 호출하지 않음 — MainWindow에서 처리.
        """
        n = self.spin_proc.value()
        arrival_times = []
        burst_times   = []

        for i in range(n):
            arrival_item = self.table.item(i, 1)
            burst_item   = self.table.item(i, 2)
            arrival_times.append(arrival_item.text() if arrival_item else "0")
            burst_times.append(burst_item.text()     if burst_item   else "1")

        return {
            "num_processes" : n,
            "num_p_cores"   : self.spin_p.value(),
            "num_e_cores"   : self.spin_e.value(),
            "arrival_times" : arrival_times,
            "burst_times"   : burst_times,
            "algorithm"     : self.combo_algo.currentText(),
            "time_quantum"  : self.spin_tq.value() if self.combo_algo.currentText() == "RR" else None,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 출력 위젯
# ══════════════════════════════════════════════════════════════════════════════

class OutputWidget(QGroupBox):
    """Gantt 차트 + 결과 테이블 + 소비전력 출력 영역."""

    def __init__(self, parent=None):
        super().__init__("출력", parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # ── Gantt 차트 ────────────────────────────────────────────────────
        layout.addWidget(QLabel("Gantt Chart:"))
        self.gantt_widget = GanttWidget()
        layout.addWidget(self.gantt_widget)

        # ── 결과 테이블 ───────────────────────────────────────────────────
        layout.addWidget(QLabel("프로세스별 결과:"))
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(
            ["PID", "WT (대기시간)", "TT (반환시간)", "NTT (정규화 반환)", "소비전력 (W)"]
        )
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setFixedHeight(200)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 읽기 전용
        layout.addWidget(self.result_table)

        # ── 소비전력 ──────────────────────────────────────────────────────
        row = QHBoxLayout()
        row.addWidget(QLabel("총 소비전력:"))
        self.lbl_power = QLabel("—")
        self.lbl_power.setStyleSheet("font-weight: bold; font-size: 14px;")
        row.addWidget(self.lbl_power)
        row.addStretch()
        layout.addLayout(row)

        self.setLayout(layout)

    def update_results(self, processes: list, gantt: list, power: float):
        """
        알고리즘 실행 결과를 받아 UI를 업데이트한다.

        Parameters
        ----------
        processes : list[Process] — 결과값이 채워진 프로세스 리스트
        gantt     : list[tuple]   — (pid, core_id, start, end)
        power     : float         — 총 소비전력
        """
        # Gantt 차트 업데이트
        self.gantt_widget.set_data(gantt)

        # 결과 테이블 업데이트
        self.result_table.setRowCount(len(processes))
        for row_idx, p in enumerate(sorted(processes, key=lambda x: x.pid)):
            self.result_table.setItem(row_idx, 0, QTableWidgetItem(str(p.pid)))
            self.result_table.setItem(row_idx, 1, QTableWidgetItem(str(p.waiting_time)))
            self.result_table.setItem(row_idx, 2, QTableWidgetItem(str(p.turnaround_time)))
            self.result_table.setItem(row_idx, 3, QTableWidgetItem(f"{p.normalized_turnaround_time:.2f}"))
            self.result_table.setItem(row_idx, 4, QTableWidgetItem("—"))  # 프로세스별 전력은 미구현

        # 소비전력
        self.lbl_power.setText(f"{power:.2f} W")


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CPU 스케줄링 시뮬레이터")
        self.setMinimumSize(800, 700)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        layout  = QVBoxLayout()

        self.input_widget  = InputWidget()
        self.output_widget = OutputWidget()

        # 실행 버튼 연결
        self.input_widget.btn_run.clicked.connect(self._on_run)

        layout.addWidget(self.input_widget)
        layout.addWidget(self.output_widget)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _on_run(self):
        """실행 버튼 클릭 시 호출."""
        inputs = self.input_widget.get_inputs()

        # ── 유효성 검사 ───────────────────────────────────────────────────
        errors = []

        err = validate_num_cores(
            inputs["num_p_cores"] + inputs["num_e_cores"],
            inputs["num_p_cores"]
        )
        if err:
            errors.append(err)

        err = validate_arrival_times(inputs["arrival_times"], inputs["num_processes"])
        if err:
            errors.append(err)

        err = validate_burst_times(inputs["burst_times"], inputs["num_processes"])
        if err:
            errors.append(err)

        if inputs["algorithm"] == "RR":
            err = validate_time_quantum(inputs["time_quantum"])
            if err:
                errors.append(err)

        if errors:
            QMessageBox.warning(self, "입력 오류", "\n".join(errors))
            return

        # ── SimConfig 생성 ────────────────────────────────────────────────
        try:
            config = parse_inputs(
                num_processes = inputs["num_processes"],
                num_p_cores   = inputs["num_p_cores"],
                num_e_cores   = inputs["num_e_cores"],
                arrival_times = inputs["arrival_times"],
                burst_times   = inputs["burst_times"],
                algorithm     = inputs["algorithm"],
                time_quantum  = inputs["time_quantum"],
            )
        except ValueError as e:
            QMessageBox.warning(self, "설정 오류", str(e))
            return

        # ── 알고리즘 실행 ─────────────────────────────────────────────────
        algo_map = {
            "FCFS": fcfs,
            "RR"  : rr,
            "SPN" : spn,
            "SRTN": srtn,
            "HRRN": hrrn,
        }

        schedule = algo_map.get(config.algorithm)

        if schedule is None:
            QMessageBox.warning(self, "알림", f"{config.algorithm}은 아직 구현되지 않았습니다.")
            return

        try:
            processes, gantt, power = schedule(config)
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", str(e))
            return

        # ── 결과 출력 ─────────────────────────────────────────────────────
        self.output_widget.update_results(processes, gantt, power)


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()