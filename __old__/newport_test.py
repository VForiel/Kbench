#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 16 11:24:54 2025

@author: photonics
"""

import time
from newportESP import ESP
import serial

dev = serial.Serial("/dev/ttyUSB1", 921600, timeout=0.1)
# msg = "1TP\r\n".encode()
# msg = "1TS\r\n".encode()
# msg = "1OR\r\n".encode()
msg = "1HT?\r\n".encode()
# msg = "1TP\r\n".encode()
# msg = "1PA90\r\n".encode() # Move qbsolute pos 180
# msg2 = "1TB000032\r\n".encode()
dev.write(msg)
time.sleep(0.2)
print(dev.readline().decode())

# dev.write(msg2)
# dev.write(msg2)
# time.sleep(0.2)
# print('Error', dev.readline().decode())

# dev.close()


# class AG27P:

#     def __init__(self, port:str):
#         self.com_port = port
#         self.open_device()
            
#     def open_device(self):

#         try:
#             self.dev = serial.Serial(port=self.com_port, baudrate=921600, bytesize=8, parity='N', 
#                                         stopbits=1, xonxoff=True, timeout=2)
#         except:
#             print("Failed to find device on {0}".format(self.port))
        
#     def close_device(self):
#         if self.dev!=None:
#             self.dev.close()
         
#     def say_hello(self):

#         if self.dev != None:
#             self.dev.write(b"1VE\r\n")
#             response = self.dev.readline()

#             if len(response)>0 and b"CONEX" in response:
#                 print("Hello 27P actuator!", response)
#             else:
        
#                 print("CONEX 27P not OK!")
#         else:
#             print("CONEX 27P not opened")

#     def _get_status(self):
#         self.dev.write(b"1TS\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()
#         return line[3:-4], line[-4:-2]
    
#     def _get_motion_status(self):
#         _, msg = self._get_status()
#         if msg==b"1E" or msg==b'28':
#             return 1
#         else:
#             return 0

#     def _get_error(self):
#         self.dev.write(b"1TE\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()   
#         return line, line[3:-2]         

#     def _get_error_message(self, message):
#         cmd = "1TB{0}\r\n".format(message.decode()).encode('ascii')
#         print(cmd)
#         self.dev.write(cmd)
#         line = self.dev.readline()   
#         return line   

#     def _get_lrange(self):
#         self.dev.write(b"1SL?\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()   
#         return float(line[3:-2])

#     def _get_urange(self):
#         self.dev.write(b"1SR?\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()   
#         return float(line[3:-2])

#     def reset(self):
#         self.dev.write(b"RS\r\n")

#     def check_reset(self):
#         _, sta = self._get_status()
#         if sta == "0A":
#             return True
#         else:
#             return False

#     def init(self):
#         self.low_lim = self._get_lrange()
#         self.up_lim = self._get_urange()
#         warn, mess = self._get_status()
#         if mess == b"3D" or mess == b'3C' :
#             self.reset()
#             time.sleep(2.)
#         if mess == b"0B" or mess==b'0E':
#             self.home()

#     def home(self):
#         self.dev.write(b"1OR\r\n")

#     def set_position(self, position):
#         if position >= self.low_lim and position <= self.up_lim:
#             cmd = "1PA{0}\r\n".format(position).encode('ascii')
#             self.dev.write(cmd)
#             time.sleep(0.2)
            
#         else:
#             print("Position {2} should be between {0} and {1}".format(self.low_lim, self.up_lim, position))

#     def _get_curr_pos(self):
#         self.dev.write(b"1TP\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()   
#         return float(line[3:-2]) 

#     def _get_target_pos(self):
#         self.dev.write(b"1TH\r\n")
#         time.sleep(0.2)
#         line = self.dev.readline()   
#         return float(line[3:-2]) 