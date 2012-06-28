#!/usr/bin/env python3

import SimPy.Simulation
from XValue import *
from Collector import Collector

class Simulation (SimPy.Simulation.Simulation):
    def __init__(self, startTime = 0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sharedObjects = {}
        self.startTime = startTime
        self.xcontext = XValueContext(lambda: self.now() + self.startTime)
        self.t = self.xcontext.t
        self.collector = Collector()
        self.tcounter = 0
        self.returnSignal = SimPy.Simulation.SimEvent("return from subroutines")

        
    def __getattr__(self, name):
        if name in self.collector.categories:
            return self.collector.categories[name]
        else:
            raise AttributeError("unknown attribute") 
        initialAmount
    def getTId(self):
        self.tcounter += 1
        return self.tcounter

    

