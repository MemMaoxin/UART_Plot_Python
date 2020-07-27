import serial
import serial.tools.list_ports
import argparse
import time
import numpy as np

from multiprocessing import Process
from multiprocessing import Array  # 共享内存
from multiprocessing import Value  # 共享内存


def calculateResistant(voltage, ref_r0 = 51, ref_vtg = 1023):
	return voltage / ref_r0 / (ref_vtg - voltage)

def connect_serial(baudrate, port=None):
	# 查看可用端口
	port_list = serial.tools.list_ports.comports()
	if len(port_list) == 0:
		print("无可用串口")
	else:
		print("所有串口：")
		for item in port_list:
			print(item)

	# 连接端口并可视化数据，如果未指定端口，则默认使用端口列表中的最后一个端口
	if not port:
		port = port_list[-1].device

	# 超时设置,None：永远等待操作，0为立即返回请求结果，其他值为等待超时时间(单位为秒）
	ser = serial.Serial(port, baudrate, timeout=None)
	print("串口详情参数：", ser)
	return ser

def process_recv_serial(data_raw, flag_raw, baudrate, port):
	ser = connect_serial(baudrate, port)
	data_tmp = []
	cnt = 0
	check_size = 100
	last_time = time.time()
	while True:
		a_char = ord(ser.read())
		if a_char == 255:
			if len(data_tmp) == 256:
				# 直接循环拷贝值，不需要加锁
				for i, item in enumerate(data_tmp):
					## 幅度提高了1000倍，方便可视化
					data_raw[i] = 1000 * item
				flag_raw.value += 1
			cnt += 1
			data_tmp = []
			if cnt == check_size:
				print(f"read fps: {check_size / (time.time() - last_time)}")
				last_time = time.time()
				cnt = 0
		else:
			data_tmp.append(calculateResistant(a_char))

def main(args):
	## shared variables
	data_raw = Array('d', 256)  # d for double
	flag_raw = Value('i')  # i for int
	flag_raw.value = 0

	p = Process(target=process_recv_serial, args=(data_raw, flag_raw, args.baudrate, args.port,))
	p.start()

	data_target = data_raw  # 表示用来可视化的数据
	## 如果需要做校准和平滑，新开进程处理之，并更新用来可视化的数据矩阵的引用
	if not args.raw:
		## new shared variables
		data_matrix = Array('d', 256)  # d for double
		flag_mat = Value('i')  # i for int
		flag_mat.value = 0

		data_target = data_matrix
		from transform import process_transform
		p1 = Process(target=process_transform, args=(data_raw, flag_raw, data_matrix, flag_mat,))
		p1.start()
		print("Data mode: calibrated and smoothed")
	else:
		print("Data mode: raw")

	if args.visualize:
		if args.matplot:
			from visual_matplot import process_visualize
			print("Activate visualization using matplotlib")
		else:
			from visual_pg import process_visualize
			print("Activate visualization using pyqtgraph")
		## visualization must be in main process
		process_visualize(data_target, 10)

	p.join()
	if not args.raw:
		p1.join()


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--port', dest='port', action='store')
	parser.add_argument('-b', '--baudrate', dest='baudrate', action='store', default=1000000, type=int)
	parser.add_argument('-v', '--visualize', dest='visualize', action='store_true', default=True)
	parser.add_argument('-m', '--matplot', dest='matplot', action='store_true', default=False)
	parser.add_argument('-r', '--raw', dest='raw', action='store_true', default=False)
	args = parser.parse_args()

	main(args)
