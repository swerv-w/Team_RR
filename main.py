import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic

form_class = uic.loadUiType("untitled.ui")[0]

class Process:
    def __init__(self, pid, arrival_time, burst_time):
        self.pid = pid
        self.at = arrival_time
        self.bt = burst_time
        self.ft = 0
        self.tat = 0
        self.wt = 0

class WindowClass(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle("Process Scheduling Simulator (FCFS)")
        self.pushButton.setText("FCFS 시뮬레이션 실행")
        self.pushButton.clicked.connect(self.run_fcfs)

        self.process_data = [
            ("P1", 0, 3),
            ("P2", 2, 6),
            ("P3", 4, 4),
            ("P4", 6, 5),
            ("P5", 8, 2)
        ]

    def run_fcfs(self):
        processes = [Process(pid, at, bt) for pid, at, bt in self.process_data]
        processes.sort(key=lambda x: x.at)

        current_time = 0
        result_text = "<b>[ FCFS 스케줄링 결과 ]</b><br><br>"
        gantt_chart = "<b>Gantt Chart:</b><br>| "

        for p in processes:
            if current_time < p.at:
                current_time = p.at

            start_time = current_time
            p.ft = start_time + p.bt
            p.tat = p.ft - p.at
            p.wt = p.tat - p.bt
            current_time = p.ft

            result_text += f"• {p.pid}: FT={p.ft}, TAT={p.tat}, WT={p.wt}<br>"
            gantt_chart += f" {p.pid} ({start_time}-{p.ft}) |"

        avg_tat = sum(p.tat for p in processes) / len(processes)
        avg_wt = sum(p.wt for p in processes) / len(processes)

        result_text += f"<br><b>평균 TAT: {avg_tat:.2f}</b>"
        result_text += f"<br><b>평균 WT: {avg_wt:.2f}</b><br><br>"
        result_text += gantt_chart

        self.textBrowser_result.setHtml(result_text)
        self.textBrowser_result.setStyleSheet("font-size: 11pt; font-family: Consolas;")
        print("FCFS 시뮬레이션 완료")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()
    app.exec_()