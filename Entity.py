#!/usr/bin/env python3

from SimPy.Simulation import *
from XValue import *
import random
from Collector import Collector
import sys
from TimeUtil import *

class InvalidXMLException(Exception):
    "invalid structure in XML input data"
    def __init__(self, msg):
        super().__init__(msg)
        
class EntityError:
    def __init__(self, msg):
        super().__init__()

def getXValue(xmlSource, tag, context):
    node = xmlSource.find(tag)
    if node is None:
        raise InvalidXMLException("undefined attribute {0}".format(tag))
    subNode = node.find("*")
    if subNode is None:
        ntext = node.text.strip() 
        if ntext != "":
            if(all(c in "0123456789" for c in ntext)):
                return XValue(int(ntext), context)
            else:
                return XValue(float(ntext), context)
        else:
            raise InvalidXMLException("empty attribute value")
    if subNode.tag == "normal":
        mu = float(subNode.get("mu", 0.0))
        sigma = float(subNode.get("sigma", 1.0))
        return XValue(lambda: random.normalvariate(mu, sigma), context)
    if subNode.tag == "pnormal":
        mu = float(subNode.get("mu", 0.0))
        sigma = float(subNode.get("sigma", 1.0))
        return XValue(lambda: max(random.normalvariate(mu, sigma), 0.0), context)        
    elif subNode.tag == "uniform":
        mn = float(subNode.get("min", 0.0)) 
        mx = float(subNode.get("max", 1.0))
        return XValue(lambda: random.uniform(mn, mx), context)
    elif subNode.tag == "exponential":
        lamda = float(subNode.get("lambda", 1.0))
        return XValue(lambda: random.expovariate(lamda), context)
    else:
        raise InvalidXMLException("unsupported attribute value")


class Entity:
    def __init__(self, transaction, xmlSource):
        self.id = xmlSource.commonId
        self.transaction = transaction
        self.simulation = transaction.simulation
        self.xcontext = XValueContext(lambda: self.simulation.now() - self.startTime)
        self.startTime = None
        self.t = self.xcontext.t

    def action(self):
        raise NotImplementedError("Abstract method")
        
    def hold(self, duration):
        return hold, self.transaction, float(duration)
        
    def __hash__(self):
        return hash(str(self.__class__)+self.id)
        
    def __str__(self):
        return "ENTITY {0} {1}".format(self.__class__.__name__, self.id)
        
class SharedEntity (Entity):
    """
        Base class for entities which use shared resource of any kind.
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        if not self.id in self.simulation.sharedObjects:
            self.simulation.sharedObjects[self.id] = self.createSharedObject(xmlSource)
    
    def createSharedObject(self, xmlSource):
        raise NotImplementedError("Abstract method")
        
    @property
    def sharedObject(self):
        return self.simulation.sharedObjects[self.id]
        

class ResourceEntity (SharedEntity):
    """
        Base class for entities based on object of Simpy Resource class (shared object limited
        by number of simultaneous access)
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def request(self):
        return request, self.transaction, self.sharedObject
    
    def release(self):
        return release, self.transaction, self.sharedObject 
        
        
class LevelEntity (SharedEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)

    def get(self, amount):
        return get, self.transaction, self.sharedObject, amount
    
    def put(self, amount):
        return put, self.transaction, self.sharedObject, amount

        
class TransactionEntity(Entity):
    """
        Base class for simple entities which don't use shared resource (i.e. per transaction entity)
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
           

class Measure:
    """
    Specification of property which is collected for statistical processing or visualisation
    (after simulation)
    
    Attributes:
        property -- specification of source of collected property in the form [a|t|s].attribute
                    a = actor property
                    t = transaction property
                    s = (global) simulation property
        category -- identification of targeted collector (if not specified = property specification)
        type -- type of collecting mechanism:
            supported mechanisms:
                stat = simple statistics (mean, min, max, std. deviation) with O(1) memory demand
                counter = counter of different values of property
                list = list of all values O(n) memory demands
                log = log to stderr (format: sim.time: category: property-spec=property-value [key])
            
        key -- if specified, the collector supports more subcollectors, which are specified by value
               of key property (typically this is actor or transaction id).
    """
    def __init__(self, measureNode):
        self.propSpec = measureNode.get("property")
        self.property = tuple(self.propSpec.split("."))
        self.key = tuple(measureNode.get("key").split(".")) if "key" in measureNode.attrib else None
        self.category = measureNode.get("category", self.propSpec)
        self.kind = Collector.types.index(measureNode.get("type"))
    
class Checkpoint(TransactionEntity):
    """
    Auxiliary entity for collecting properties of simulated system.
    Collected values and mechanisms of collecting are specified by measure subelements
    (see class Measure)
    """
    def __init__(self, transaction, xmlSource):
       super().__init__(transaction, xmlSource)
       self.measures = [Measure(node) for node in xmlSource]
       self.referedEntity = xmlSource.get("referedEntity", None)
    
    def action(self):
        yield self.hold(0)
        for measure in self.measures:
            prop = self._getProperty(measure.property)
            key = None
            if measure.key is not None:
                key = self._getProperty(measure.key)
            if measure.kind == Collector.LOG:
                keystr = "({0})".format(key) if key is not None else ""
                print("{0}: {1} {2}={3} {4}"
                      .format(dtstr(self.simulation.t),
                              measure.category,
                              measure.propSpec,
                              prop,
                              keystr),
                      file=sys.stderr)    
            else:
                self.simulation.collector.collect(measure.category, prop, measure.kind, key)
            
    def _getProperty(self, prop):
        obj = None
        if prop[0] == "a":
            obj = self.transaction.actor
        if prop[0] == "t":
            obj = self.transaction
        elif prop[0] == "s":
            obj = self.simulation
        elif prop[0] == "e":
            obj = self.referedEntity
        elif prop[0] == "eso":
            obj = self.referedEntity.sharedObject
        return getattr(obj, prop[1])
            
                    
