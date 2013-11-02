#!/usr/bin/env python3

import multiprocessing
from Etos import *
import ECarModel
import Pause
import numpy as np
import sys

registerModule(ECarModel)
registerModule(Pause)



def taskF(request):
    sim = Simulation()
    sim.disableLog()
    sim.setParameters(**request)
    sim.start("XML/e-car-inwest.xml#transaction[@id='starter']")
    print("hotovo {0}".format(request["stations"]), file=sys.stderr)
    return (request["stations"], request["shoppingProbability"], sim.batteryOut[1.0])

#print(multiprocessing.cpu_count())    
pool = multiprocessing.Pool()
tasks = (dict(cars=200, stations=s, shoppingProbability=sp) for s in range(20, 210, 8)
                                                            for sp in np.arange(0.0, 1.1, 0.1))

for result in pool.imap_unordered(taskF, tasks):
    print("\t".join(str(item) for item in result))
