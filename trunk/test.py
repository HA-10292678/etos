#!/usr/bin/env python3

import Etos
from Transaction import Transaction
from TimeUtil import *
from UrlUtil import xmlLoader
            
sim = Etos.Simulation(startTime=float(strdt("0:00:00")))
sim.initialize()

transactionNode = xmlLoader("XML/gastrans.xml#transaction[@id='starter']")
t =  Transaction(transactionNode, sim)
sim.activate(t, t.run(), at = 0)

sim.simulate(until=int(DayTime(minutes=40)))

#print("mean: " + dtstr(sim.totalDuration.mean))
#print("stdvar: " + dtstr(sim.totalDuration.standardDeviation))
#print("min: " + dtstr(sim.totalDuration.min))
#print("max: " + dtstr(sim.totalDuration.max))
#print(sim.tStarted)
#print(sim.tFinished)
    
