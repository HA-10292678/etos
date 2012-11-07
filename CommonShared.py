#!/usr/bin/env python3

from SimPy.Simulation import *
from Entity import ResourceEntity
from XValue import getXValue, XValueHelper

class Alarm(Process):
    """
        The trigger process which reactivates a process when the reneging delay time has passed
        Based on http://simpy.sourceforge.net/reneging.htm
    """
    def __init__(self, transaction):
        super().__init__(sim=transaction.simulation)
        self.transaction = transaction
    
    def wakeup(self, delay):
            yield hold, self, delay
            self.transaction.simulation.reactivate(self.transaction)
            yield hold, self  #unclear semantics

class LimitedWaitingResourceEntity (ResourceEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.alarm = None
        self.maxWaiting = getXValue(xmlSource, "queue_waiting", self.xcontext)
        self.duration = getXValue(xmlSource, "duration", self.xcontext)
        self.usedResource = False
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "resources",
                             XValueHelper(self, XValueHelper.SIMULATION_CONTEXT))
        return Resource(int(capacity), sim=self.simulation)
        
    def action(self):
        self.alarm = Alarm(self.transaction)
        self.simulation.activate(self.alarm, self.alarm.wakeup(delay=float(self.maxWaiting)))
        yield self.request()
        if self.gotResource():
            yield self.hold(float(self.duration))
            yield self.release()
            self.usedResource = True 

    def gotResource(self): #(c) http://simpy.sourceforge.net/reneging.htm
        """Tests whether the resource has been acquired"""
        result=self.transaction in self.sharedObject.activeQ
        if result:
            #Acquired, so cancel alarm
            self.transaction.cancel(self.alarm)
        else:
            #not acquired, so get out of queue, renege
            self.sharedObject.waitQ.remove(self.transaction)
            #FIXME: monotoring 
        return result
    
class OneShotProcess(Process):
    def __init__(self, simulation, generator, delay = 0.0):
        super().__init__(sim=simulation)
        self.generator = generator
        self.delay = delay

    def shot(self):
        yield hold, self, self.delay
        yield next(self.generator)

class SharedObjectsContainer:
    def __init__(self, **kwargs):
        self.objects = kwargs

    def __getattr__(self, attribute):
        return self.objects[attribute]    

