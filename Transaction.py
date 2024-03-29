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
    def __init__(self, eType):
        self.type = eType
        
 
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
    """
    Representation of simulation process (including subprocesses).
    Key attributes:
        self.tid =
            identification of instance of top level transaction (transaction-id)
        self.pid =
            internal identifier of internal simulation process (i.e. id of instance of subprocess)
        self.template =
            (optional) identification of transaction template (processed by transaction instances)
    """
    def __init__(self,  transactionXmlNode, simulation, tid = None, ppid = None,
                 entitiesXmlNode = None, actor = None, entities = None, xcontext = None):
        super().__init__(sim=simulation)
        self.simulation = simulation
        try:
            self.entitiesXmlNode = entitiesXmlNode if entitiesXmlNode is not None else XmlSource()
            self.template = transactionXmlNode.get("id")
            self.pid = self.simulation.getTId()
            self.id = tid if tid is not None else self.pid
            self.ppid = ppid

            if actor is not None:
                self.actor = actor
            else:
                path, base = transactionXmlNode.getWithBase("actor")
                if path is not None:
                    self.actor = Actor(self.simulation,
                                       xmlLoader(path, base=base), extraProperties = True)
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
        Abstract base class for entities which controls some subentities.
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.valueNodes = []
        self.entityIndex = None
        self.iterationIndex = None
    
    def populateSubEntities(self, entityNode):
        factory =  EntityFactory(entityNode)
        self.subentities = populateSubTransactions(factory, self.transaction,
                                                   self.xmlSource, self.valueNodes)
        
    def setTransaction(self, transaction):
        self.transaction = transaction
        for subentity in self.subentities:
            subentity.setTransaction(transaction)
            
    def attributeSetter(self, *attrlist):
        for attrName, typ in attrlist:
            setattr(self, attrName, typ(getXValue(self.xmlSource, attrName, XValueHelper(self))))
            self.valueNodes.append(attrName)
     
    def validateSubentities(self):
        return len(self.subentities) > 0
    
    def nextSubEntity(self, exception):
        raise NotImplementedError("Abstract method")
    
    def nextIteration(self):
        raise NotImplementedError("Abstract method")
    
    def handledException(self, exception):
        raise NotImplementedError("Abstract method")
    
    def action(self):
        if not self.validateSubentities():
            raise AttributeError("Control entity with none subentity")
        self.entityIndex = -1
        self.iterationIndex = -1
        while self.nextIteration():
            exception = None
            while self.nextSubEntity(exception):
                entity = self.subentities[self.entityIndex]
                with entity.xcontext:
                    i = iter(entity.action())
                    while True:
                        try: 
                            event = next(i)
                            if isinstance(event, ExceptionEvent) and self.handledException(event):
                                exception = event
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
                                             
     
class Loop(ControlEntity):
    """
        Abstract base class for loop constructs.
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.restartException = xmlSource.get("restart")
    
    def nextSubEntity(self, exception):
        if exception is not None:
            return False
        self.entityIndex += 1
        return self.entityIndex < len(self.subentities)

    def nextIteration(self):
        self.iterationIndex += 1
        if self.test():
            self.entityIndex = -1
            return True
        return False
    
    def handledException(self, exception):
        return exception.type == self.restartException
    
    def test(self):
        "loop condition (at start, if true loop continues)"
        raise NotImplementedError("Abstract method")
    
     
     
class InfinityLoop (Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def test(self):
        return True
    
class CountedLoop(Loop):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.attributeSetter(("count", int))
            
    def test(self):
        return self.iterationIndex < self.count
    
    
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
            
            
class NonIterationControl(ControlEntity):
    """
        Abstract base class for non-loop control entities.
        Non-loop constructs support only **limited** number of subentities (typically 1 or 2)
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def nextIteration(self):
        self.iterationIndex += 1
        return self.iterationIndex == 0

class Block(NonIterationControl):
    """
        Block entity combines several subentities to one (top level) entity.
        The block entity adds new level of indirection for coroutine yielding
        but is useful for non-loop controls ().
        
        
        Declarative element: block
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        
    def handledException(self, exception):
        return False
    
    def nextSubEntity(self, exception):
        assert exception is None
        self.entityIndex += 1
        return self.entityIndex < len(self.subentities)
            
class TryCatch(NonIterationControl):
    """
        Try-catch constructs (catching and handling of exception)
        
        Subentities:
        ------------
        # try section
        # exception handler (catch section), optional
        
        Declarative element: try_catch
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.exceptionType = xmlSource.get("exception")
        
    def handledException(self, exception):
        return self.entityIndex == 0 and exception.type == self.exceptionType

    def nextSubEntity(self, exception):
        if self.entityIndex == -1: #enter try section
            self.entityIndex = 0
            return True
        if self.entityIndex == 0 and exception is not None:
            self.entityIndex = 1   #go to catch section
            return True
        return False #else leave try-catch
     
    def validateSubentities(self):
        return len(self.subentities) == 2
            
class Branching(NonIterationControl):
    """
        Abstract base class for branching constructs.
            
        Subentities:
        ------------
        # if section
        # else section
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
    
    def handledException(self, exception):
        return False
    
    def nextSubEntity(self, exception):
        assert exception is None
        if self.entityIndex >= 0:
            return False
        if self.test():
            self.entityIndex = 0
            return True
        if len(self.subentities) == 2:
            self.entityIndex = 1
            return True
        return False
    
    def validateSubentities(self):
        return 1 <= len(self.subentities) <= 2
    
    def test(self):
        """branching condition (if true the if-section is executed)"""
        raise NotImplementedError("Abstract method")
    
class WithProbability(Branching):
    """
        If-section (= first subentity) is executed with given probability (0, 1).
        or optional else-section (second subentity) with complementary probability (1-p).
        
        Declarative element: with
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.attributeSetter(("probability", float))
        
    def test(self):
        x = random.random()
        return x  < self.probability
    
class If(Branching):
    """
       If-section (= first subentity) is executed if property is interpreted as true
       (normal Python boolean semantics), otherwise else-section is only executed.
       
       Declarative element: if
    """
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
    """
        New top level transaction is created and started (it runs independently on
        parent transaction).
            
         Declarative element: start_transaction   
    """
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
        self.returnSignal = None
            
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

