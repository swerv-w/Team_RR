import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
from models.process import Process
form_class = uic.loadUiType("untitled.ui")[0]

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()
    sys.exit(app.exec_())
