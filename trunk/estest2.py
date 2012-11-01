#!/usr/bin/env python3

from Etos import *
import ECarModel
import Pause

registerModule(ECarModel)
registerModule(Pause)
sim = Simulation()
sim.start("XML/e-car_Alpha.xml#transaction[@id='starter']")
