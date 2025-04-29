import serial
from time import sleep

zabr = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)

zabr.write("/2 get pos\r\n".encode())
print(zabr.readline().decode())
# @01 0 OK IDLE FS 10000

# sleep(5)
# zabr.write("/1 move abs 292680\r\n".encode())
# print(zabr.readline().decode())
# # @01 0 OK BUSY FS 0

# zabr.write("/1 get pos\r\n".encode())
# print(zabr.readline().decode())
# # @01 0 OK IDLE FS 500

zabr.close()
