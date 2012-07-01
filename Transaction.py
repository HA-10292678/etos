#!/usr/bin/env python3

from SimPy.Simulation import *
from UrlUtil import xmlLoader, XmlSource
from XValue import XValueContext
import uuid
import traceback
import sys

from Entity import *
from Model import *
 
def populateEntities(factory, transaction, xmlNode):
    entities = [factory.createFromXml(node, transaction, base) for node,base in xmlNode.iterWithBased()]
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
            self.actor = actor
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stderr)
        
 
    def run(self): #SimPy PEM method
        self.startTime = self.simulation.now()
        for entity in self.entities:
            entity.startTime = self.simulation.now()
            with entity.xcontext:
            # in Python 3.3 could be transfer to "yield from self.action"
                i = iter(entity.action())
                while True:
                    try:
                        event = next(i)
                        yield event
                    except StopIteration:
                        break
                    except BaseException as e:
                        print("EXCEPTION : {0}".format(str(e)))
                        traceback.print_exc(file=sys.stderr)
                        #sys.exit()
        if self.ppid is not None:
            self.simulation.returnSignal.signal(self.ppid)
        
    @staticmethod
    def fromFiles(transactionFile, entitiesFile, simulation):
        transactionRoot = ET.parse(transactionFile).getroot()
        entitiesRoot = ET.parse(entitiesFile).getroot()
        return Transaction(transactionRoot, entitiesRoot, simulation)
        
class ControlEntity(Entity):
    """
        Abstract base class for entity, which control some subentities
    """
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        self.xmlSource = xmlSource
        self.subentities = None 
    
    def populateSubEntities(self, entityNode):
        factory =  EntityFactory(entityNode)
        self.subentities = populateEntities(factory, self.transaction, self.xmlSource)
     
class Loop(ControlEntity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
    
    def action(self):
        while self.test():
            for entity in self.subentities:
                with entity.xcontext:
                    i = iter(entity.action())
                    while True:
                        try:
                            event = next(i)
                            yield event
                        except StopIteration:
                            break
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
            

class TransactionEntity(Entity):
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
                        entitiesXmlNode=self.entitiesNode, actor = self.transaction.actor)
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
            finishedSubtrans = self.simulation.returnSignal.signalparam

class EntityFactory:
    stdMapping = dict(checkpoint = Checkpoint, infinity_loop = InfinityLoop,
                      counted_loop = CountedLoop, start_transaction = StartTransaction,
                      transaction = SubTransaction)
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
    

