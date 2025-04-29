#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 22 11:14:36 2025

@author: photonics
"""

import serial
import time

class Newport:
    def __init__(self, port, axis, baudrate=921600):
        """
        Instance the object and open the serial connection to the device.

        Parameters
        ----------
        port : string
            Port of the device.
        axis : int
            Axis of the device to actuate.
        baudrate : int
            Baud rate. Defqult value is 921600.
            
        Examples
        --------
        >>> newp = Newport("/dev/ttyUSB1", 1, 921600) # Port is open

        """
        self.com_port = port
        self.baud_rate = baudrate
        self.dev = None
        self.axis = str(axis)
        self.open_device()

        self.low_lim = self._get_lrange()
        self.up_lim = self._get_urange()
        
    def open_device(self):
        """
        Open the port connection to the device.
        """
        try:
            self.dev = serial.Serial(port=self.com_port, baudrate=self.baud_rate,
                                     bytesize=8, parity='N',
                                     stopbits=1, xonxoff=True, timeout=2)
            print('Port is open')
        except:
            print("Failed to find device on {0}".format(self.com_port))
            
    def close(self):
        """
        Close the port to the device.
        """
        if self.dev != None:
            self.dev.close()
            print('Port is closed')

    def _encode_cmd(self, cmd):
        cmd = self.axis + cmd + "\r\n"
        cmd = cmd.encode()
        return cmd
    
    def _send_command(self, cmd):
        self.dev.write(cmd)
        time.sleep(0.2)
        out = self.dev.readline().decode()
        return out
    
    def _get_lrange(self):
        cmd = self._encode_cmd("SL?")
        out = self._send_command(cmd) 
        return float(out[3:-2])

    def _get_urange(self):
        cmd = self._encode_cmd("SR?")
        out = self._send_command(cmd) 
        return float(out[3:-2])
    
    def get_pos(self):
        """
        Display current status and current position of the axis.
        It also returns the current position.

        Returns
        -------
        pos : float
            Current position.

        Examples
        --------
        >>> newp = Newport("/dev/ttyUSB1", 1, 921600) # Port is open
        >>> pos = newp.get_pos() # Current position: xxxxx
        """
        cmd = self._encode_cmd("TP")
        out = self._send_command(cmd)
        pos = float(out[3:-2])
        print("Current position:", pos)
        return pos
        
    def homing(self):
        """
        Home the axis.
        Only works if the device lost the position (i.e. after powering up).
        So this command may not work if everything is fine.
        
        Examples
        --------
        >>> newp = Newport("/dev/ttyUSB1", 1, 921600) # Port is open
        >>> newp.homing() # Going to home position
        """
        print("Going to home position")
        cmd = self._encode_cmd("OR")
        self._send_command(cmd)
        
    def move_abs(self, abs_pos):
        """
        Move the axis to the absolute position.
        
        If nothing is triggered, try homing the device.

        Parameters
        ----------
        abs_pos : float
            Absolute position to reach by the axis.

        Returns
        -------
        None.

        Examples
        --------
        >>> newp = Newport("/dev/ttyUSB1", 1, 921600) # Port is open
        >>> newp.move_abs(120) # Move to absolute position: 120
        """
        if abs_pos >= self.low_lim and abs_pos <= self.up_lim:
            print("Move to absolute position:", abs_pos)
            cmd = self._encode_cmd("PA" + str(abs_pos))
            self._send_command(cmd)
        else:
            print("Position {2} should be between {0} and {1}".format(self.low_lim, self.up_lim, abs_pos))        

    def move_rel(self, rel_pos):
        """
        Move the axis by a relative position.
        
        If nothing is triggered, try homing the device.

        Parameters
        ----------
        rel_pos : float
            Relative position to move by by the axis.
            It can be positive or negative.

        Returns
        -------
        None.

        Examples
        --------
        >>> newp = Newport("/dev/ttyUSB1", 1, 921600) # Port is open
        >>> newp.move_rel(-20) # Move of relative position: -20
        """
        curr_pos = self.get_pos()
        target_pos = curr_pos + rel_pos
        if target_pos >= self.low_lim and target_pos <= self.up_lim:
            print("Move of relative position:", rel_pos)
            cmd = self._encode_cmd("PR"+ str(rel_pos))
            self._send_command(cmd)
        else:
            print("Target position {2} should be between {0} and {1}".format(self.low_lim, self.up_lim, target_pos))
            
wait_time = 11. / 40.
port = "/dev/ttyUSB1"
baudrate = 921600
newp = Newport(port, 1, baudrate)
pos = newp.get_pos()
print("Lower limit", newp.low_lim)
print("Upper limit", newp.up_lim)
newp.move_abs(350)
time.sleep(wait_time*20)
pos2 = newp.get_pos()
# newp.move_rel(-40)

