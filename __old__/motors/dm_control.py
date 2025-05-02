#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 23 17:01:18 2025

@author: photonics
"""

import bmc

class DM:
	def __init__(self, shm_DMptt = "/dev/shm/phot_DM.00.shm", 
		shm_DMptt_cor = "/dev/shm/phot_DM.01.shm",
		shm_DMptt_atmo = "/dev/shm/phot_DM.02.shm",
		DMSerialNumber="27BW007#051"
        ""):