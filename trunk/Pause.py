#!/usr/bin/env python3

from Entity import SimpleEntity
from XValue import getXValue, number
from PropertyGetter import Property
import math

class Pause(SimpleEntity):
    """
    Simulation of simple pause with specified duration.
    """
    tag = "pause"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.duration = getXValue(xmlSource, "duration", self.xcontext)
        
    def action(self):
        yield self.hold(self.duration)
        
        
class PauseTo(SimpleEntity):
    tag = "pause_to"
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.epoch = Property(xmlSource.get("epoch", "s.t"))
        self.period = xmlSource.get("period", None)
        if self.period is not None:
            self.period = number(self.period)
        self.time = getXValue(xmlSource, "time", self.xcontext)
        if self.period is not None:
            assert self.time < self.period
        assert 0 <= self.time
        
    def duration(self):
        ptime = self.time
        atime = float(self.epoch.get(self.transaction, self))
        if self.period is not None:
            comper = math.floor(atime / self.period)
            start = comper * self.period
            rem = atime - start
            if ptime < rem:
                start += self.period
            ptime = start + ptime
        return ptime - atime
        
    def action(self): 
        yield self.hold(self.duration())    
