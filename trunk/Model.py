#!/usr/bin/env python3

from SimPy.Simulation import *
from Entity import *

class FuelStation(ResourceEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        return Resource(int(capacity), sim=self.simulation)
        
    def action(self):
        yield self.request()
        yield self.hold(40)
        yield self.release()


class Connection(TransactionEntity):
    """
        Simulation of simple passage from point A to B
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.distance = getXValue(xmlSource, "distance", self.xcontext)
        self.velocity = getXValue(xmlSource, "velocity", self.xcontext)

    def action(self):
        t = self.distance / self.velocity
        yield self.hold(t)
        
class Pause(TransactionEntity):
    """
    Simulation of simple pause with specified duration.
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.duration = getXValue(xmlSource, "duration", self.xcontext)
        
    def action(self):
        yield self.hold(self.duration)
        
class Alarm(Process):
    """
        The trigger process which reactivates a process when the reneging delay time has passed
        Based on http://simpy.sourceforge.net/reneging.htm
    """
    def __init__(self, transaction):
        super().__init__(transaction.simulation)
        self.transaction = transaction
    
    def wakeup(self, delay):
            yield hold, self, delay
            reactivate(self.transaction)
            yield hold, self  #unclear semantics                  
                    
class Parking (ResourceEntity):
    """
        Simulation of parking lot with limited number of parking places (capacity) and limited
        waiting time, if the parking lot is full.
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.alarm = None
        self.maxWaiting = getXValue(xmlSource, "maxWaiting", self.xcontext)
        self.duration = getXValue(xmlSource, "duration", self.xcontext)
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        return Resource(int(capacity), sim=self.simulation)
        
    def action(self):
        self.alarm = Alarm(self.transaction)
        self.simulation.activate(self.alarm, self.alarm.wakeup(delay=float(self.maxWaiting)))
        yield self.request()
        if self.gotResource():
            yield self.hold(float(self.duration))
            yield self.release()
        #else the car isn't using parking lot 

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
        
class Tanking(LevelEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.refuel= getXValue(xmlSource, "amount", self.xcontext)
        
    def createSharedObject(self, xmlSource):
        capacity = getXValue(xmlSource, "capacity", self.simulation.xcontext)
        self.initialAmount = getXValue(xmlSource, "initialAmount", self.simulation.xcontext)
        if float(self.initialAmount) > float(capacity):
            raise Exception("Initial amount greater than capacity")
        level = Level(capacity=float(capacity),sim=self.simulation)
        resource=Resource(sim=self.simulation)
        lev=LevelAdapter(level,resource)
        if float(self.initialAmount)>0:	
            init = OneShotProcess(self.simulation, self.initAction())
            self.simulation.activate(init, init.shot())
        return lev

    def action(self):
        yield self.request()
        if self.sharedObject.patience==True and self.sharedObject.amount<float(self.refuel):
            yield self.get(self.sharedObject.amount)
            if len(self.sharedObject.waitQ)!=0:
                for x in self.sharedObject.waitQ:
                    self.sharedObject.waitQ.put()
        else:
            yield self.get(float(self.refuel))
        yield self.hold(10)
        yield self.release()
        
    def initAction(self):
        yield self.put(float(self.initialAmount))
        
class OneShotProcess(Process):
    def __init__(self, simulation, generator, delay = 0.0):
        super().__init__(sim=simulation)
        self.generator = generator
        self.delay = delay

    def shot(self):
        yield hold, self, self.delay
        yield next(self.generator)

class UniversalResource(object):
    def request(self):
        raise NotImplementedError
    def release(self):
        raise NotImplementedError
    def put(self):
        raise NotImplementedError
    def get(self):
        raise NotImplementedError
    
class LevelAdapter(UniversalResource):
    def __init__(self, level, resource, patience=True):
        self.level=level
        self.resource=resource
        self.patience=patience
    
    def request(self):
        return request
    def release(self):
        return release
    def put(self):
        return put
    def get(self):
        return get
    def __getattr__(self,attr):
        try:
            return getattr(self.level,attr)
        except Exception:
            return getattr(self.resource,attr)
    
    