#!/usr/bin/env python3

import Etos
from Transaction import Transaction
from TimeUtil import *
from UrlUtil import xmlLoader
from Dumper import *
import sys
            
sim = Etos.Simulation(startTime=float(strdt("0:00:00")))
sim.initialize()

transactionNode = xmlLoader("XML/gastrans.xml#transaction[@id='starter']")
t =  Transaction(transactionNode, sim)
sim.activate(t, t.run(), at = 0)

sim.simulate(until=int(DayTime(days=1)))

#for transaction in sim.tanking.keys():
#    print("{0}:mean={1.mean}".format(transaction,sim.tanking[transaction]),file=sys.stderr)  



    
