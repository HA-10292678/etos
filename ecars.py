#!/usr/bin/env python3

from Etos import *
import ECarModel
import Pause
from Dumper import Dumper


registerModule(ECarModel)
registerModule(Pause)
sim = Simulation()
sim.start("XML/e-car_Beta.xml#transaction[@id='starter']")

d = Dumper()
print(d.dump(sim.outOfCharge))
