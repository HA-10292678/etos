#!/usr/bin/env python3

import SimPy.Simulation
import Transaction
import Entity
from UrlUtil import xmlLoader
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
        self.returnSignal = SimPy.Simulation.SimEvent("return from subroutines", sim=self)
        self.initialize()
        self.xvalues = {}
        self.logging = True


    def start(self, transaction, duration = 0xFFFFFFFF):
        if isinstance(transaction, str):
            transaction = Transaction.Transaction(xmlLoader(transaction), self)
        self.activate(transaction, transaction.run())
        self.simulate(until=int(duration))
        

    def setParameter(self, key, value):
        self.xvalues[key] = value if isinstance(value, XValue) else XValue(value)
        
    def getParameter(self, key):
        return self.xvalues[key]

    def __getattr__(self, name):
        if name in self.collector.categories:
            return self.collector.categories[name]
        else:
            raise AttributeError("unknown attribute") 
        initialAmount
    def getTId(self):
        self.tcounter += 1
        return self.tcounter
    
    def disableLog(self):
        self.logging = False
    
def registerModule(module):
    Transaction.EntityFactory.registerModule(module)

    

