#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 17 15:29:14 2025

@author: photonics
"""

import serial
import time

class SerialMotor:
    def __init__(self, port, baudrate):
        self.com_port = port
        self.baud_rate = baudrate
        self.dev = None
        self.open_device()
        
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
        out = self.dev.readline().decode()
        return out
    
class Zaber(SerialMotor):
    def __init__(self, port, axis, baudrate=115200):
        """
        Instance the object and open the serial connection to the device.

        Parameters
        ----------
        port : string
            Port of the device.
        baudrate : int
            Baud rate. Default value is 115200.
        axis : int
            Axis of the device to actuate.

        Returns
        -------
        None.

        Examples
        --------
        >>> zab = Zaber("/dev/ttyUSB0", 1, 115200) # Port is open
        """
        super().__init__(port, baudrate)
        self.axis = "/"+str(axis)
        
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
        >>> zab = Zaber("/dev/ttyUSB0", 1, 115200) # Port is open
        >>> pos = zab1.get_pos() # Get position: pos
        >>> print(pos) # xxxxxxx
        """
        cmd = self._encode_cmd(" get pos")
        out = self._send_command(cmd)
        pos = int(out.split()[-1])
        print("Get position:", pos)
        return pos
        
    def homing(self):
        """
        Home the axis.
        """
        print("Going to home position.")
        cmd = self._encode_cmd(" home")
        self._send_command(cmd)
        
    def move_abs(self, abs_pos):
        """
        Move the axis to the absolute position.

        Parameters
        ----------
        abs_pos : int
            Absolute position to reach by the axis.
            If it is float type, it is converted into an integer.

        Returns
        -------
        None.

        Examples
        --------
        >>> zab = Zaber("/dev/ttyUSB0", 1, 115200) # Port is open
        >>> zab.move_abs(1000) # Move to the absolute position: abs_pos
        >>> zab.get_pos() # Get position: pos
        """
        print("Move to the absolute position:", abs_pos)
        cmd = self._encode_cmd(" move abs "+ str(int(abs_pos)))
        self._send_command(cmd)

    def move_rel(self, rel_pos):
        """
        Move the axis by a relative position.

        Parameters
        ----------
        rel_pos : int
            Relative position to move by by the axis.
            It can be positive or negative.
            If it is float type, it is converted into an integer.

        Returns
        -------
        None.

        Examples
        --------
        >>> zab = Zaber("/dev/ttyUSB0", 1, 115200) # Port is open
        >>> zab.move_rel(50000) # Move by the relative position: rel_pos
        >>> zab.get_pos() # Get position: pos
        """
        print("Move by the relative position:", rel_pos)
        cmd = self._encode_cmd(" move rel "+ str(rel_pos))
        self._send_command(cmd)

class Newport(SerialMotor):
    def __init__(self, port, axis, baudrate=921600):
        """
        Instance the object and open the serial connection to the device.

        Parameters
        ----------
        port : string
            Port of the device.
        baudrate : int
            Baud rate. Default value is 921600.
        axis : int
            Axis of the device to actuate.

        Returns
        -------
        None.

        Examples
        --------
        >>> zab = Zaber("/dev/ttyUSB0", 1, 921600) # Port is open
        """        
        super().__init__(port, baudrate)
        self.axis = str(axis)
        
        self.low_lim = self._get_lrange()
        self.up_lim = self._get_urange()

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
        

print("ZABER")
port = "/dev/ttyUSB0"
baudrate = 115200
zab1 = Zaber(port, 1, baudrate)
zab2 = Zaber(port, 2, baudrate)
pos1 = zab1.get_pos()
pos2 = zab2.get_pos()
# zab1.move_rel(50000)
# zab1.move_abs(292680)
# zab2.move_abs(1000)
# zab1.move_abs(100000)
# zab2.move_rel(50000)

print(" ")
print("NEWPORT")
wait_time = 11. / 40.
newp = Newport("/dev/ttyUSB1", 1, 921600)
pos = newp.get_pos()
# print("Lower limit", newp.low_lim)
# print("Upper limit", newp.up_lim)

# newp.move_abs(110)

