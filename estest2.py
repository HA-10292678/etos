#!/usr/bin/env python3

from Etos import *
import Model
import Pause

registerModule(Model)
registerModule(Pause)
sim = Simulation()
sim.start("XML/e-car_Alpha.xml#transaction[@id='starter']")
