import Etos
from Transaction import Transaction
from TimeUtil import *
from UrlUtil import xmlLoader
from Dumper import *


sim = Etos.Simulation(startTime=float(strdt("0:00:00")))
sim.initialize()

transactionNode = xmlLoader("XML/subtrans.xml")
t =  Transaction(transactionNode, sim)
sim.activate(t, t.run())

sim.simulate(until=int(DayTime(days=1)))
