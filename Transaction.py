#!/usr/bin/env python3

from SimPy.Simulation import *
from UrlUtil import xmlLoader, XmlSource
from XValue import *
from PropertyGetter import Property
import uuid
import traceback
import sys
import random

from Entity import *
from Model import *
from Actor import Actor

 
def populateEntities(factory, transaction, xmlNode):
    entities = [factory.createFromXml(node, transaction, base)
                    for node,base in xmlNode.iterWithBased()]
    for i in range(len(entities)):
        if not isinstance(entities[i], Checkpoint) or entities[i].referedEntity is None:
            continue
        if entities[i].referedEntity == "prev" and i > 0:
            entities[i].referedEntity = entities[i-1]
        elif entities[i].referedEntity == "next" and i < len(entities) - 1:
            entities[i].referedEntity = entities[i+1]
        else:
            raise Exception("Invalid referention to refered entity [checkpoint]")
    return entities

def populateSubTransactions(factory, transaction, xmlNode):
    entities = [factory.createFromXml(node, transaction, base)
                    for node,base in xmlNode.iterWithBased() if node.tag == "transaction"]
    return entities
 
class Transaction(Process):
    def __init__(self,  transactionXmlNode, simulation, tid = None, ppid = None, entitiesXmlNode = None,
                 actor = None):
        super().__init__(sim=simulation)
        self.simulation = simulation
        try:
            self.entitiesXmlNode = entitiesXmlNode if entitiesXmlNode is not None else XmlSource()
            self.pattern = transactionXmlNode.get("id")
            self.pid = self.simulation.getTId()
            self.id = tid if tid is not None else self.pid
            self.ppid = ppid
        
            path, base = transactionXmlNode.getWithBase("entities")
            if path is not None:
                self.entitiesXmlNode.append(xmlLoader(path, base=base))
            self.factory = EntityFactory(entitiesXmlNode)
            self.entities = populateEntities(self.factory, self, transactionXmlNode)
            self.startTime = None
            self.xcontext = XValueContext(lambda: self.simulation.now() - self.startTime)
            self.t = self.xcontext.t
            if actor is not None:
                self.actor = actor
            else:
                path, base = transactionXmlNode.getWithBase("actor")
                if path is not None:
                    self.actor = Actor(self.simulation, xmlLoader(path, base=base),
                                       extraProperties = True)
                else:
                    self.actor = Actor(self.simulation, XmlSource())
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stderr)
        
 
    def run(self): #SimPy PEM method
        self.startTime = self.simulation.now()
        interrupted = False
        for entity in self.entities:
            entity.startTime = self.simulation.now()
            with entity.xcontext:
            # in Python 3.3 could be transfer to "yield from self.action"
                generator = entity.action() 
                i = iter(generator)
                while True:
                    try:
                        event = next(i)
                        if event is None:
                            interrupted = True
                            break
                        yield event
                    except StopIteration:
                        break
                    except BaseException as e:
                        print("EXCEPTION : {0}".format(str(e)))
                        traceback.print_exc(file=sys.stderr)
                if interrupted:
                    break
        if not self.topLevel:
            self.simulation.returnSignal.signal((self.ppid, interrupted))

    @property 
    def topLevel(self):
        return self.ppid is None
        
    @staticmethod
    def fromFiles(transactionFile, entitiesFile, simulation):
        transactionRoot = ET.parse(transactionFile).getroot()
        entitiesRoot = ET.parse(entitiesFile).getroot()
        return Transaction(transactionRoot, entitiesRoot, simulation)
        
class ControlEntity(SimpleEntity):
    """
        Abstract base class for entity, which control some subtransactions
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.xmlSource = xmlSource
    
    def populateSubEntities(self, entityNode):
        factory =  EntityFactory(entityNode)
        self.subentities = populateSubTransactions(factory, self.transaction, self.xmlSource)
     
class Loop(ControlEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
    
    def action(self):
        assert len(self.subentities) == 1
        while self.test():
            entity = self.subentities[0]
            with entity.xcontext:
                i = iter(entity.action())
                while True:
                    try:
                        event = next(i)
                        yield event
                    except StopIteration:
                        break
                    except GeneratorExit:
                        return
                    except BaseException as e:
                        print("EXCEPTION : {0}".format(str(e)))
                        traceback.print_exc(file=sys.stderr)
                        sys.exit()
    
    def test(self):
        raise NotImplementedError("Abstract method")
     
     
class InfinityLoop (Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def test(self):
        return True
    
class CountedLoop(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.count = 0
        self.limit = int(getXValue(xmlSource, "count", self.xcontext))
            
    def test(self):
        self.count += 1
        return self.count <= self.limit
    
    
class While(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.property = Property(xmlSource.get("property")) 
    
    def test(self):
        return bool(self.property.get(self.transaction, self))

    
class WhileInRange(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.property = Property(xmlSource.get("property")) 
        self.minimum = float(getXValue(xmlSource, "minimum", self.xcontext))
        self.maximum = float(getXValue(xmlSource, "maximum", self.xcontext))
        
    def test(self):
        value = float(self.property.get(self.transaction, self))
        return self.minimum <= value <= self.maximum
            
            
class Branching(ControlEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
    
    def action(self):
        assert len(self.subentities) in (1,2)
        if self.test():
            entity = self.subentities[0]
        elif len(self.subentities) == 2:
            entity = self.subentities[1]
        else:
            return
            
        with entity.xcontext:
            i = iter(entity.action())
            while True:
                try:
                    event = next(i)
                    yield event
                except StopIteration:
                    break
                except GeneratorExit:
                    return
                except BaseException as e:
                    print("EXCEPTION : {0}".format(str(e)))
                    traceback.print_exc(file=sys.stderr)
                    sys.exit()
    
    def test(self):
        raise NotImplementedError("Abstract method")
    
class WithProbability(Branching):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.probability = float(getXValue(xmlSource, "probability", self.xcontext))
        
    def test(self):
        x = random.random()
        return x  < self.probability
    
class If(Branching):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.property = Property(xmlSource.get("property")) 
    
    def test(self):
        return bool(self.property.get(self.transaction, self))
    
class IfInRange(Branching):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.property = Property(xmlSource.get("property")) 
        self.minimum = float(getXValue(xmlSource, "minimum", self.xcontext))
        self.maximum = float(getXValue(xmlSource, "maximum", self.xcontext))
        
    def test(self):
        value = float(self.property.get(self.transaction, self))
        return self.minimum <= value <= self.maximum    
    

class TransactionEntity(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        if xmlSource.get("transactionUrl") is not None:
            path, base = xmlSource.getWithBase("transactionUrl")
            if path is  None:
                raise Exception("No trans URL")
            self.transactionNode = xmlLoader(path, base=base)
            path, base = xmlSource.getWithBase("entityUrl")
            if path is None:
                self.entitiesNode = XmlSource([self.transaction.entitiesXmlNode])
            else:
                self.entitiesNode = xmlLoader(path, base=base)
        else:
            self.transactionNode = xmlSource
            self.entitiesNode = XmlSource([self.transaction.entitiesXmlNode])

        
class StartTransaction(TransactionEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
       
        
    def action(self):
        t = Transaction(self.transactionNode, simulation=self.simulation,
                        entitiesXmlNode=self.entitiesNode, actor = None)
        self.simulation.activate(t, t.run(), at = 0)
        
class SubTransaction(TransactionEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
            
    def action(self):
        t = Transaction(self.transactionNode, simulation=self.simulation,
                        tid = self.transaction.id, ppid = self.transaction.pid,
                        entitiesXmlNode = self.entitiesNode, actor = self.transaction.actor)
        self.simulation.activate(t, t.run(), at = 0)
        finishedSubtrans = -1
        while finishedSubtrans != self.transaction.pid:
            yield waitevent, self.transaction, self.simulation.returnSignal
            finishedSubtrans = self.simulation.returnSignal.signalparam[0]
            interrupted = self.simulation.returnSignal.signalparam[1]
        if interrupted:
            try:
                yield None
            except GeneratorExit:
                return

class ExitTransaction(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def action(self):
        try:
            yield None
        except GeneratorExit:
            return
        
class StopSimulation(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def action(self):
        yield self.hold(0)
        self.simulation.stopSimulation()
        
class SetEntity(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.value = getXValue(xmlSource, "value", self.xcontext)
        self.property = Property(xmlSource.get("property"))
    
    def action():
        yield self.hold(0)
        self.property.set(self.transaction, self, float(self.value))
  
class EntityFactory:
    stdMapping = dict({ "if" : If, "while" : While, "with" : WithProbability},
                      checkpoint = Checkpoint,
                      trace = Trace,
                      infinity_loop = InfinityLoop,
                      counted_loop = CountedLoop,
                      start_transaction = StartTransaction,
                      transaction = SubTransaction,
                      while_in_range = WhileInRange,
                      if_in_range = IfInRange,
                      exit = ExitTransaction,
                      stop_simulation = StopSimulation,
                      set = SetEntity)
    def __init__(self, entityNode, mapping = None):
        if mapping is None:
            mapping = EntityFactory.stdMapping
        self.mapping = mapping
        self.root = entityNode
        
    @staticmethod
    def register(cls, tagName=None):
        tagName = tagName if tagName is not None else cls.tag
        EntityFactory.stdMapping[tagName] = cls
        
    @staticmethod    
    def registerModule(module):
        for cls in module.__dict__.values():
            if hasattr(cls, "tag"):
                EntityFactory.register(cls)
                
        
    def createFromXml(self, transactionNode, transaction, base = None):
        eType = transactionNode.tag
        source = XmlSource()
        source.append(transactionNode, base)
        eId = transactionNode.get("id", None)
        if eId is not None:
            externalNode = self.root.find("{0}[@id='{1}']".format(eType, eId))
            if externalNode is not None:
                source.append(externalNode)
        entity = self.mapping[eType](transaction, source)
        if isinstance(entity, ControlEntity):
            entity.populateSubEntities(self.root)
        return entity      

