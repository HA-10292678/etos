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
    def __init__(self, transactionXmlNode, simulation, entitiesXmlNode = None , actor = None):
        super().__init__(sim=simulation)
        self.simulation = simulation
        try:
            self.entitiesXmlNode = entitiesXmlNode if entitiesXmlNode is not None else XmlSource()
            self.pattern = transactionXmlNode.get("id")
            self.id = self.simulation.getTId()
        
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
                        sys.exit()
        
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
        self.subentities = populateEntities(factory, self.transaction,
                                            self.xmlSource.find("transaction"))
     
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
            
        
class StartTransaction(Entity):
    def __init__(self, transaction, xmlSource):
        super().__init__(transaction, xmlSource)
        print(xmlSource)
        path, base = xmlSource.getWithBase("transactionUrl")
        if path is  None:
            raise Exception("No trans URL")
        self.transactionNode = xmlLoader(path, base=base)
        path, base = xmlSource.getWithBase("entityUrl")
        if path is None:
            self.entitiesNode = XmlSource([self.transaction.entitiesXmlNode])
        else:
            self.entitiesNode = xmlLoader(path, base=base)
        
        
    def action(self):
        t = Transaction(self.transactionNode, self.simulation, self.entitiesNode)
        self.simulation.activate(t, t.run(), at = 0)  
        

class EntityFactory:
    stdMapping = dict(connection=Connection, pause=Pause, refuel=FuelStation, tank=SimpleTanking,
                      rtank=ResourceTanking,
                      checkpoint = Checkpoint, parking = Parking, infinity_loop = InfinityLoop,
                      counted_loop = CountedLoop, start_transaction = StartTransaction)
    def __init__(self, entityNode, mapping = None):
        if mapping is None:
            mapping = EntityFactory.stdMapping
        self.mapping = mapping
        self.root = entityNode
        
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
    

