#!/usr/bin/env python3

import multiprocessing
from Etos import *
import ECarModel
import Pause
from Dumper import Dumper

registerModule(ECarModel)
registerModule(Pause)



def taskF(request):
    sim = Simulation()
    sim.disableLog()
    sim.setParameters(**request)
    sim.start("XML/e-car-inwest.xml#transaction[@id='starter']")
    d = Dumper() 
    #return request["cars"], request["stations"], d.dump(sim.batteryOut)
    return request["cars"], request["stations"], d.dump(sim.batteryOut)
    
pool = multiprocessing.Pool()
tasks = (dict(cars=c, stations=s, shoppingProbability=0.5) for c in range(1,5) for s in range(1,5))

for result in pool.imap_unordered(taskF, tasks):
    print("\t".join(str(item) for item in result))
