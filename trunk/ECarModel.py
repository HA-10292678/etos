#!/usr/bin/env python3
from Actor import Actor
from Entity import *
from XValue import getXValue, number
from Pause import PauseTo
from CommonShared import LimitedWaitingResourceEntity, Alarm

class Route(SimpleEntity):
    tag="route"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.distance = getXValue(xmlSource, "distance", self.xcontext) #km 
        self.velocity = getXValue(xmlSource, "velocity", self.xcontext) #km/h
        
        self.limit = getXValue(xmlSource, "limit", self.xcontext) #0.0-1.0
        self.delay = getXValue(xmlSource, "delay", self.xcontext) #sec
        
    def action(self):
        duration = self.distance / self.velocity * 60 * 60
        
        yield self.hold(duration)
        
        actor = self.transaction.actor.props
        energy = self.distance /  actor["consumption"]
        
        cEnergy = actor["consumption"] * self.distance
        actor["energy"] -= cEnergy
        
        if (actor["energy"] <= 0 or actor["energy"] / actor["capacity"] <= self.limit):
            yield self.hold(self.delay)
            actor["energy"] = 0.5 *  actor["capacity"]
            actor["outOfCharge"] = 1
    
def charging(voltage, current, energy, capacity, duration):
        energy += voltage * current * (duration / 3600.0) / 1000.0 #v kWh
        return capacity if energy > capacity else energy
    
class HomeCharging (PauseTo):
    tag="homeCharging"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.voltage = getXValue(xmlSource, "voltage", self.xcontext)
        self.current = getXValue(xmlSource, "current", self.xcontext)
        
    def action(self):
        duration = self.duration()
        yield self.hold(duration)
        
        actor= self.transaction.actor.props
        actor["energy"] = charging(self.voltage, self.current, actor["energy"],
                                   actor["capacity"], duration)

        
class FastCharging(LimitedWaitingResourceEntity):
    tag="fastCharging"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.voltage = getXValue(xmlSource, "voltage", self.xcontext)
        self.current = getXValue(xmlSource, "current", self.xcontext)
    
    def action(self):
        # yield from super().action()
        shopTime = float(self.duration)
        self.alarm = Alarm(self.transaction)
        self.simulation.activate(self.alarm, self.alarm.wakeup(delay=float(self.maxWaiting)))
        yield self.request()
        if self.gotResource():
            yield self.hold(shopTime)
            yield self.release()
            self.usedResource = True
        else:
            yield self.hold(shopTime)
        
        if self.usedResource:    
            actor = self.transaction.actor.props
            actor["energy"] = charging(self.voltage, self.current, actor["energy"],
                                   actor["capacity"], shopTime)
        
        
        
        
        
        
