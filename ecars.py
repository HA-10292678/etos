#!/usr/bin/env python3

from Etos import *
import ECarModel
import Pause

registerModule(ECarModel)
registerModule(Pause)
sim = Simulation()
#sim.disableLog()
sim.setParameters(cars=2, stations=2, shoppingProbability=0.5)
sim.start("XML/e-car-inwest.xml#transaction[@id='starter']")

print(sim.batteryOut[1.0])
