# 时间：2020.5.1
# 适用于第一版测温板
import pyqtgraph as pg
import array
import serial
import threading
import numpy as np
from queue import Queue
import time
from PyQt5 import QtWidgets
import sys
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import Qt

i = 0
control = 0
data_length = 500
curve = []
data = []
data_bytes = bytearray()
pw = []
que = []
index_now = []
process = []
f = []
velocity = 0
label = []
rate = 0
mean_array1 = np.zeros(100)
mean_index1 = 0
mean_array2 = np.zeros(100)
mean_index2 = 0


def serial_xx():
    global data_bytes
    global f, control
    global rate, mean_array1, mean_array2, mean_index1, mean_index2
    while True:
        count = mSerial.inWaiting()
        if count:
            rec_str = mSerial.read(count)
            data_bytes = data_bytes + rec_str
            data_len = len(data_bytes)
            k = 0
            while k + 21 < data_len:
                if data_bytes[k] == 0XFF and ((data_bytes[k + 19] == 0XAA and data_bytes[k + 20] == 0XAA) or (
                        data_bytes[k + 19] == 0XDD and data_bytes[k + 20] == 0XDD)):
                    t = time.time()
                    rate = rate + 1
                    if control:
                        f.write(str(round(t * 1000)) + ' ')

                    Vref = 0
                    Vt1 = 0
                    Vt2 = 0
                    for k2 in range(3):
                        for k3 in range(3):
                            data_put = data_bytes[k + 1 + k3 * 2 + 6 * k2] * 256 + data_bytes[k + 2 + k3 * 2 + 6 * k2]
                            if data_put > 5000:
                                data_put = 0
                            if k3 == 0:
                                Vref = data_put
                            if k3 == 1:
                                Vt1 = data_put
                            if k3 == 2:
                                Vt2 = data_put
                            que[k3].put(data_put)
                            if control:
                                f.write(str(data_put) + ' ')
                        if Vref != 0:
                            if data_bytes[k + 19] == 0XAA:
                                Rt1 = Vt1 * 30100 / Vref
                                mean_array1[mean_index1 % 100] = Rt1
                                mean_index1 += 1
                                Rt1 = np.mean(mean_array1)
                                que[4].put(Rt1)
                            else:
                                Rt2 = Vt2 * 30100 / Vref
                                mean_array2[mean_index2 % 100] = Rt2
                                mean_index2 += 1
                                Rt2 = np.mean(mean_array2)
                                que[5].put(Rt2)

                    if control:
                        if data_bytes[k + 19] == 0XAA:
                            f.write(str(0XAA) + ' ')
                        else:
                            f.write(str(0XDD) + ' ')
                        f.write('\r\n')

                    k = k + 21
                    data_bytes[0:k] = b''
                    data_len = len(data_bytes)
                    k = 0
                else:
                    k = k + 1
            data_bytes[0:k] = b''


class MainWidget(QtWidgets.QMainWindow):
    def action_save(self):
        global f
        global control
        global rate, velocity, label

        if self.pushButton.text() == "SaveData":
            self.pushButton.setText("StopSaveData")
            fileName2, ok2 = QFileDialog.getSaveFileName(self,
                                                         "文件保存",
                                                         "./",
                                                         "Text Files (*.txt)")
            if not fileName2:
                fileName2 = "test1111.txt"
            f = open(fileName2, 'w')
            f.write('abcd')
            control = 1
        elif self.pushButton.text() == "StopSaveData":
            self.pushButton.setText("SaveData")
            control = 0
            f.close()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImpedanceData")  # 设置窗口标题
        main_widget = QtWidgets.QWidget()  # 实例化一个widget部件
        main_layout = QtWidgets.QGridLayout()  # 实例化一个网格布局层
        main_widget.setLayout(main_layout)  # 设置主widget部件的布局为网格布局

        for k, graph_title in zip(range(6),
                                  ['Vref(OUTC-OUTB)', 'Vt1(OUTA-OUTC)', 'Vt2(OUTD-OUTC)', 'NULL', 'RT1阻值', 'RT2阻值']):
            pw.insert(k, pg.PlotWidget(title=graph_title))
            data.insert(k, array.array('i'))
            data[k] = np.zeros(data_length).__array__('d')
            que.insert(k, Queue(maxsize=0))
            index_now.insert(k, 0)
            label.insert(k, QtWidgets.QLabel())
            label[k].setAlignment(Qt.AlignCenter)
            label[k].setText(' Efficiency:  0 %')

        for k, p, d, color in zip(range(6), pw, data, ['r', 'g', 'y', 'b', 'm', 'c']):
            curve.insert(k, (p.plot(d, pen=color)))
            p.setRange(yRange=[0, 2050])
            main_layout.addWidget(pw[k], 1 + 2 * int(k / 2), 1 + (k % 2))  # 添加绘图部件到网格布局层
            main_layout.addWidget(label[k], 2 + 2 * int(k / 2), 1 + (k % 2))
        pw[4].setRange(yRange=[25000, 65000])
        pw[5].setRange(yRange=[25000, 65000])
        self.pushButton = QtWidgets.QPushButton(main_widget)
        self.pushButton.setText("SaveData")
        self.pushButton.clicked.connect(self.action_save)
        main_layout.addWidget(self.pushButton, 9, 1, 1, 2)
        self.setCentralWidget(main_widget)  # 设置窗口默认部件为主widget


def consumer(a):
    while True:
        if index_now[a] < data_length:
            data[a][index_now[a]] = que[a].get()
            index_now[a] = index_now[a] + 1

        else:
            data[a][:-1] = data[a][1:]
            data[a][index_now[a] - 1] = que[a].get()


def plot_data():
    for k in range(6):
        curve[k].setData(data[k])


def rate_refresh():
    global rate, velocity, label, SD_open
    for k in range(6):
        velocity = rate - velocity
        valid = velocity * 2
        velocity = rate
        label[k].setText(' Efficiency:   %')


if __name__ == "__main__":
    # port_xx = input('请输入端口号,比如COM4:  ')
    # bps = input('请输入波特率,比如9600:  ')
    # 串口执行到这已经打开 再用open命令会报错
    # mSerial = serial.Serial(port_xx, int(bps))
    mSerial = serial.Serial('COM9', 57600)
    if mSerial.isOpen():
        print("open success")
        mSerial.flushInput()  # 清空缓冲区

    else:
        print("open failed")
        mSerial.close()  # 关闭端口
    app = QtWidgets.QApplication(sys.argv)
    gui = MainWidget()
    th1 = threading.Thread(target=serial_xx)
    th1.start()
    gui.show()
    timer = pg.QtCore.QTimer()
    timer.timeout.connect(plot_data)  # 定时刷新数据显示
    timer.start(30)  # 多少ms调用一次
    timer1 = pg.QtCore.QTimer()
    timer1.timeout.connect(rate_refresh)  # 定时刷新数据显示
    timer1.start(3000)  # 多少ms调用一次

    for k1 in range(6):
        process.insert(k1, threading.Thread(target=consumer, args=(k1,)))
        process[k1].start()
    sys.exit(app.exec_())
