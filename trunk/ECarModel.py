#!/usr/bin/env python3
from Actor import Actor
from Entity import *
from XValue import getXValue, number, XValueHelper
from Pause import PauseTo
from CommonShared import LimitedWaitingResourceEntity, Alarm

class Route(SimpleEntity):
    tag="route"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.distance = getXValue(xmlSource, "distance", XValueHelper(self)) #km 
        self.velocity = getXValue(xmlSource, "velocity", XValueHelper(self)) #km/h
        
        self.limit = getXValue(xmlSource, "limit", XValueHelper(self), 0.0) #0.0-1.0
        self.delay = getXValue(xmlSource, "delay", XValueHelper(self)) #sec
        # output properties
        self.duration = None
        self.consumedEnergy = None
        self.batteryOut = False
        
    def action(self):
        duration = self.distance / self.velocity * 60 * 60
        self.duration = duration        
        yield self.hold(duration)
        
        actor = self.transaction.actor.props
        energy = self.distance /  actor["consumption"]
        
        cEnergy = actor["consumption"] * self.distance
        self.consumedEnergy = min(cEnergy, actor["energy"])
        actor["energy"] -= cEnergy
        
        if (actor["energy"] <= 0 or actor["energy"] / actor["capacity"] <= self.limit):
            yield self.hold(self.delay)
            actor["energy"] = 0.5 *  actor["capacity"]
            actor["batteryOutEvent"] = 1.0
            self.batteryOut = True
    
def simpleCharging(voltage, current, energy, capacity, duration):
        energy += 0.8 * voltage * current * (duration / 3600.0) / 1000.0 #v kWh
        return capacity if energy > capacity else energy

def charging(voltage, current, energy, capacity, duration):
	c = capacity * 1000 #to Wh	
	d = duration / 3600.0 #to hour
	ideal_time = c / (voltage * current * 0.9)
	x = d / ideal_time
	renergy = min(energy/capacity + 0.168*x*x*x - 0.78*x*x +1.38*x, 1.0)
	return capacity*renergy
    
class HomeCharging (PauseTo):
    tag="homeCharging"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.voltage = getXValue(xmlSource, "voltage", XValueHelper(self))
        self.current = getXValue(xmlSource, "current", XValueHelper(self))
        #output properties
        self.chargedEnergy = None
        
    def action(self):
        duration = self.duration()
        yield self.hold(duration)
        
        actor= self.transaction.actor.props
        initialEnergy = actor["energy"]
        actor["energy"] = charging(self.voltage, self.current, actor["energy"],
                                   actor["capacity"], duration)
        self.chargedEnergy = actor["energy"] - initialEnergy

        
class FastCharging(LimitedWaitingResourceEntity):
    tag="fastCharging"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.voltage = getXValue(xmlSource, "voltage", XValueHelper(self))
        self.current = getXValue(xmlSource, "current", XValueHelper(self))
        #output properties
        self.chargedEnergy = None
    
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
            initialEnergy = actor["energy"]
            actor["energy"] = charging(self.voltage, self.current, actor["energy"],
                                   actor["capacity"], shopTime)
            self.chargedEnergy = actor["energy"] - initialEnergy
        else:
            self.chargedEnergy = 0.0
        
        
        
        
        
        
