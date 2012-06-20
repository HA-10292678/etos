#!/usr/bin/env python3
import collections
from math import sqrt

class Statistics:
    def __init__(self):
        self.s0 = 0.0
        self.s1 = 0.0
        self.s2 = 0.0
        self.max = None
        self.min = None
        
    def update(self, v):
        self.s0 += 1
        self.s1 += v
        self.s2 += v*v
        if self.max is None or v > self.max:
            self.max = v
        if self.min is None or v < self.min:
            self.min = v
            
    @property
    def count(self):
        return self.s0
        
    @property    
    def mean(self):
        return self.s1 / self.s0
    
    @property
    def standardDeviation(self):
        return sqrt((self.s0*self.s2-self.s1*self.s1)/(self.s0*(self.s0-1)))

class Collector:
    STAT=0
    COUNTER=1
    LIST=2
    LOG=3
    types = ["stat", "counter", "list", "log"]
    def __init__(self):
        self.categories = dict()
        
    def collect(self, category, prop, kind, key):
        if not category in self.categories:
            if key is not None:
                self.categories[category] = {}
            else:
                self.categories[category] = Collector._newContainer(kind)
        self._set(category, prop, kind, key)
        
    @staticmethod    
    def _newContainer(kind):
        if kind == Collector.STAT:
            return Statistics()
        elif kind == Collector.COUNTER:
            return collections.Counter()
        elif kind == Collector.LIST:
            return []
        else:
            assert False, "unknown category type {0}".format(kind)
    
    def _set(self, category, prop, kind, key):
        if key is not None:
            if not key in self.categories[category]:
                self.categories[category][key] = Collector._newContainer(kind)
            container = self.categories[category][key]
        else:
            container = self.categories[category]
        if kind == Collector.STAT:
            container.update(float(prop))    
        elif kind == Collector.COUNTER:
            container[prop] = container[prop] + 1
        elif kind == Collector.LIST:
            container.append(prop)
        else:
            assert False,  "unknown category type"
