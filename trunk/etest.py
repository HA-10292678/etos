#!/usr/bin/env python3

from Etos import *
import ECarModel

registerModule(ECarModel)   
sim = Simulation()
sim.start("XML/e-car.xml#transaction[@id='starter']")
