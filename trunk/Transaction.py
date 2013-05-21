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

class ExceptionEvent:
    def __init__(self, type):
        self.type = type
        
 
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

def populateSubTransactions(factory, transaction, xmlNode, valueNodes):
    entities = [factory.createFromXml(node, transaction, base)
                    for node,base in xmlNode.iterWithBased() if node.tag not in valueNodes]
    return entities
 
class Transaction(Process):
    def __init__(self,  transactionXmlNode, simulation, tid = None, ppid = None,
                 entitiesXmlNode = None, actor = None, entities = None, xcontext = None):
        super().__init__(sim=simulation)
        self.simulation = simulation
        try:
            self.entitiesXmlNode = entitiesXmlNode if entitiesXmlNode is not None else XmlSource()
            self.pattern = transactionXmlNode.get("id")
            self.pid = self.simulation.getTId()
            self.id = tid if tid is not None else self.pid
            self.ppid = ppid

            if actor is not None:
                self.actor = actor
            else:
                path, base = transactionXmlNode.getWithBase("actor")
                if path is not None:
                    self.actor = Actor(self.simulation, xmlLoader(path, base=base),
                                       extraProperties = True)
                else:
                    self.actor = Actor(self.simulation, XmlSource())

            self.startTime = None
            if xcontext is None:
                self.xcontext = XValueContext(lambda: self.simulation.now() - self.startTime)
            else:
                self.xcontext = xcontext
            self.t = self.xcontext.t

            path, base = transactionXmlNode.getWithBase("entities")
            if path is not None:
                self.entitiesXmlNode.append(xmlLoader(path, base=base))
            if entities is None:
                self.factory = EntityFactory(entitiesXmlNode)    
                self.entities = populateEntities(self.factory, self, transactionXmlNode)
            else:
                for entity in entities:
                    entity.setTransaction(self)
                self.entities = entities
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stderr)
        
 
    def run(self): #SimPy PEM method
        self.startTime = self.simulation.now()
        interrupted = False
        exceptionEvent = None
        for entity in self.entities:
            entity.startTime = self.simulation.now()
            with entity.xcontext:
            # in Python 3.3 could be transfer to "yield from self.action"
                generator = entity.action() 
                i = iter(generator)
                while True:
                    try:
                        event = next(i)
                        #print(self.pid, event.__class__, entity)
                        if isinstance(event, ExceptionEvent):
                            interrupted = True
                            exceptionEvent = event
                            break
                        yield event
                    except StopIteration:
                        break
                    except BaseException as e:
                        print("EXCEPTION : {0}".format(str(e)))
                        traceback.print_exc(file=sys.stderr)
                        self.simulation.stopSimulation()
                if interrupted:
                    break
        if not self.topLevel:
            self.returnSignal.signal(exceptionEvent)
        else:
            if interrupted and exceptionEvent.type != "__exit__":
                print("UNHANDLED EXCEPTION '{0}'".format(exceptionEvent.type))
            

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
        Abstract base class for entities which controls some subtransactions
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.xmlSource = xmlSource
        self.valueNodes = []
        self.iteration = 0
        self.subentity = 0
    
    def populateSubEntities(self, entityNode):
        factory =  EntityFactory(entityNode)
        self.subentities = populateSubTransactions(factory, self.transaction, self.xmlSource, self.valueNodes)
        
    def setTransaction(self, transaction):
        self.transaction = transaction
        for subentity in self.subentities:
            subentity.setTransaction(transaction)
            
    def attributeSetter(self, *attrlist):
        for attrName, typ in attrlist:
            setattr(self, attrName, typ(getXValue(self.xmlSource, attrName, XValueHelper(self))))
            self.valueNodes.append(attrName)
     
    
    def nextSubEntity(self, exception):
        pass
    
    def nextIteration(self, exception):
        pass
    
    def acceptException(self, exception):
        pass
    
    def action(self):
        exception = None
        while self.nextIteration(self, exception):
            while self.nextSubEntity(self, exception):
                entity = self.subentities[self.subentity]
                with entity.xcontext:
                    i = iter(entity.action)
                    while True:
                        try: 
                            event = next(i)
                            if isinstance(event, ExceptionEvent) and self.acceptException(event):
                                exception = event
                                break
                            yield event
                            exception = None
                        except StopIteration:
                            break
                        except GeneratorExit:
                            return
                        except BaseException as e:
                            print("EXCEPTION : {0}".format(str(e)))
                            traceback.print_exc(file=sys.stderr)
                            self.simulation.stopSimulation()
                        
                        
     
class Loop(ControlEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.restartException = xmlSource.get("restart")
    
    def action(self):
        contException = False
        while self.test():
            for entity in self.subentities:
                with entity.xcontext:
                    i = iter(entity.action())
                    while True:
                        try:
                            event = next(i)
                            if isinstance(event, ExceptionEvent) and event.type == self.restartException:
                                contException = True
                                break
                            yield event
                        except StopIteration:
                            break
                        except GeneratorExit:
                            return
                        except BaseException as e:
                            print("EXCEPTION : {0}".format(str(e)))
                            traceback.print_exc(file=sys.stderr)
                            self.simulation.stopSimulation()
                    if contException:
                        contException = False
                        break
        
    def test(self):
        raise NotImplementedError("Abstract method")
     
     
class InfinityLoop (Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def test(self):
        return True

class Block(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.open = True
        
    def test(self):
        if self.open:
            self.open=False
            return True
        else:
            return False

    
class CountedLoop(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.i = 0
        self.attributeSetter(("count", int))
            
    def test(self):
        self.i += 1
        return self.i <= self.count
    
    
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
        self.attributeSetter(("minimum", float), ("maximum", float))
        
    def test(self):
        value = float(self.property.get(self.transaction, self))
        return self.minimum <= value <= self.maximum
            
class TryCatch(ControlEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.exceptionType = xmlSource.get("exception")
        
    def action(self):
        assert len(self.subentities) == 2
        entity = self.subentities[0]
        exceptEntity = self.subentities[1]
        exceptHandler = False
        
        while True:
            with entity.xcontext:
                i = iter(entity.action())
                while True:
                    try:
                        event = next(i)
                        if (not exceptHandler
                                and isinstance(event, ExceptionEvent)
                                and event.type == self.exceptionType):
                            entity = exceptEntity
                            exceptHandler = True
                            break
                        yield event
                    except StopIteration:
                        return
                    except GeneratorExit:
                        return
                    except BaseException as e:
                        print("EXCEPTION : {0}".format(str(e)))
                        traceback.print_exc(file=sys.stderr)
                        self.simulation.stopSimulation()

            
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
                    return
                except GeneratorExit:
                    return
                except BaseException as e:
                    print("EXCEPTION : {0}".format(str(e)))
                    traceback.print_exc(file=sys.stderr)
                    self.simulation.stopSimulation()
    
    def test(self):
        raise NotImplementedError("Abstract method")
    
class WithProbability(Branching):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.attributeSetter(("probability", float))
        
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
        self.attributeSetter(("minimum", float), ("maximum", float))
        
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
        self.savedEntities = None
            
    def action(self):
        trans = Transaction(self.transactionNode, simulation=self.simulation,
                            tid = self.transaction.id, ppid = self.transaction.pid,
                            entitiesXmlNode = self.entitiesNode, actor = self.transaction.actor,
                            entities = self.savedEntities, xcontext = self.transaction.xcontext)
        if self.savedEntities is None:
            self.savedEntities = trans.entities
        self.simulation.activate(trans, trans.run(), at = 0)
        
        trans.returnSignal = SimEvent("return from subtransaction", sim=self.simulation)
        
        yield waitevent, self.transaction, trans.returnSignal
        exceptionEvent = trans.returnSignal.signalparam
        if exceptionEvent is not None:
            try:
                yield exceptionEvent
            except GeneratorExit:
                return

class ExitTransaction(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def action(self):
        try:
            yield ExceptionEvent("__exit__")
        except GeneratorExit:
            return
        
class ExceptionEntity(SimpleEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.type = xmlSource.get("type", "")
        
    def action(self):
        try:
            yield ExceptionEvent(self.type)
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
    
    def action(self):
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
                      exception = ExceptionEntity,
                      try_catch = TryCatch,
                      stop_simulation = StopSimulation,
                      block = Block,
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

