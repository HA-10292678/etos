#!/usr/bin/env python3

from SimPy.Simulation import *
from Entity import *
from XValue import *

class FuelStation(ResourceEntity):
    tag = "refuel"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        return Resource(int(capacity), sim=self.simulation)
        
    def action(self):
        yield self.request()
        yield self.hold(40)
        yield self.release()


class Connection(SimpleEntity):
    """
        Simulation of simple passage from point A to B
    """
    tag = "connection"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.distance = getXValue(xmlSource, "distance", self.xcontext)
        self.velocity = getXValue(xmlSource, "velocity", self.xcontext)

    def action(self):
        t = self.distance / self.velocity
        yield self.hold(t)
        
        

        
class ResourceTanking(SharedEntity):
    tag = "rtank"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.refuel= getXValue(xmlSource, "amount", self.xcontext)
        self.realAmount = 0.0
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        
        self.initialAmount = getXValue(xmlSource, "initialAmount", self.simulation.xcontext)
        if float(self.initialAmount) > float(capacity):
            raise Exception("Initial amount greater than capacity")
        level = Level(capacity=float(capacity),sim=self.simulation)
        resource = Resource(sim=self.simulation)
        emptyEvent = SimEvent(sim=self.simulation)
        lev=SharedObjectsContainer(tank=level,units=resource, emptyEvent=emptyEvent)
        if float(self.initialAmount)>0:	
            init = OneShotProcess(self.simulation, self.initAction())
            self.simulation.activate(init, init.shot())
        return lev
    
    def request(self):
        return ((request, self.transaction, self.sharedObject.units),
                (waitevent, self.transaction, self.sharedObject.emptyEvent))
       
    def get(self, amount):
        return get, self.transaction, self.sharedObject.tank, amount
    
    def put(self, amount):
        return put, self.transaction, self.sharedObject.tank, amount

    def release(self):
        return release, self.transaction, self.sharedObject.units
        
    def action(self):
        if self.sharedObject.tank.amount == 0.0:
            self.realAmount = 0.0
            return
        yield self.request()
        if not self.transaction.acquired(self.sharedObject.units):
            return
        try:
            if self.sharedObject.tank.amount<float(self.refuel):
                yield self.get(self.sharedObject.tank.amount)
                self.realAmount = self.sharedObject.tank.amount
                self.sharedObject.emptyEvent.signal()
            else:
                yield self.get(float(self.refuel))
                self.realAmount = float(self.refuel)
            yield self.hold(300)
        finally:
            yield self.release()
        
    def initAction(self):
            yield self.put(float(self.initialAmount))
        
class SimpleTanking(LevelEntity):
    tag = "tank"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.refuel= getXValue(xmlSource, "amount", self.xcontext)
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        self.initialAmount = getXValue(xmlSource, "initialAmount", self.simulation.xcontext)
        if float(self.initialAmount) > float(capacity):
            raise Exception("Initial amount greater than capacity")
        level = Level(capacity=float(capacity), sim=self.simulation)
        init = OneShotProcess(self.simulation, self.initAction())
        self.simulation.activate(init, init.shot())
        return level
    
    def action(self):
        yield self.get(float(self.refuel))
        
    def initAction(self):
        yield self.put(float(self.initialAmount))
    
        

    
    
    
