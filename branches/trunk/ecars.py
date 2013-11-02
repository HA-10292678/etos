#!/usr/bin/env python3

from Etos import *
import ECarModel
import Pause

registerModule(ECarModel)
registerModule(Pause)
sim = Simulation()
#sim.disableLog()
sim.setParameters(cars=100, stations=1, shoppingProbability=0.9)
sim.start("XML/e-car-inwest2.xml#transaction[@id='starter']")

print(sim.charged_f.sum / sim.charged_h.sum)

