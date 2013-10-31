#!/usr/bin/env python3

import numbers
import inspect
import operator
import random
import json
import string
import weakref
import re
import os
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.request import urlopen
import xml.etree.ElementTree as ET


def fmt(f, *params):
    replaces = []
    newparams = []
    for match in re.finditer(r"#\(([^)|]+)(\|([^)]+))?\)", f):
        start = match.start(0)
        end = match.end(0)
        body = match.group(1)
        impl = match.group(3)
        subm = re.search("{(\d+)", body)
        assert subm
        position = int(subm.group(1))
        replace = body if params[position] else (impl if impl is not None else "")
        replaces.append((start,end, replace))
        
    for start,end,replace in replaces[::-1]:
        f = f[:start] + replace + f[end:]
        
        
    return f.format(*params)

class XValueContext:
    "context for x-values (support of scope and local timescale)"
    def __init__(self, timeFunc = None):
        self.time = timeFunc #function of timescale
        self.values = weakref.WeakSet() #set of weak reference for all values of context
        
    def addValue(self, value): 
        "add value to context"
        self.values.add(value)
        
    def resetContext(self):
        "reset context in the beginning of new scope"
        for value in self.values:
            if value is not None: #if value isn't garbage-collected
                value.reset()             
        return self        

    def __enter__(self):  #implementation of context manager protocol
        self.resetContext()
    
    def __exit__(self, *exc): #implementation of context manager protocol
        return True
    
    @property
    def t(self):  #returns auxiliary x-value represented context time
        return XValue(lambda t:t, self)


class SimDslError(Exception):
    def __init__(self, fmt, *params):
        super().__init__(fmt.format(*params))

class XValueHelper:
    def __init__(self, stdContextTag):
        self.stdContextTag = stdContextTag
        
    def getContext(self, contextTag):
        return self.mapper(contextTag) if contextTag is not None else self.mapper(self.stdContextTag) 
       
    def mapper(self, contextTag):
        raise NotImplementedError("Abstract method")
    
class DummyXValueHelper(XValueHelper):
    def __init__(self, context):
        super().__init__(None)
        self.context = context
        
    def mapper(self, contextTag):
        return self.context

class XValueEntityHelper(XValueHelper):
    ENTITY_CONTEXT = 0
    TRANSACTION_CONTEXT = 1
    ACTOR_CONTEXT = 2
    SIMULATION_CONTEXT = 3
    
    def __init__(self, entity, stdContextTag = "entity"):
        super().__init__(stdContextTag)
        transaction = entity.transaction
        
        self.contexts = {"entity"       : entity.xcontext,
                         "transaction"  : transaction.xcontext,
                         "actor"        : transaction.actor.xcontext,
                         "simulation"   : transaction.simulation.xcontext}

    def mapper(self, contextTag):
        return self.context[contextTag]

def arity(func):
    return len(inspect.getargspec(func)[0])

class XValue:
    FIXED = 0
    RANDOM = 1
    TIME_DEPENDENT = 2
      
    def __init__(self, value):
        assert value is not None #null (undefined) values are not supported
        self.context = None
        if XValue.isPrimitiveType(value):
            self.type = XValue.FIXED #fixed integral, float number or bool
            self.fval = None
            self.rval = value
        elif callable(value) and arity(value) == 0: #parameterless generator
            self.type = XValue.RANDOM
            self.fval = value
            self.rval = None
        elif callable(value) and arity(value) == 1: #function of context time
            self.type = XValue.TIME_DEPENDENT
            self.fval = value
            self.rval = None
        else:
            raise SimDslError("Unsupported X-value type {0}", type(value))
        self.time = None
    
    def setContext(self, context):
        self.context =  context
        self.context.addValue(self)
    
    def reset(self): #reset random value in the begining of new scope
        if self.type == XValue.RANDOM:
            self.rval = None
               
    def _eval(self): #evaluating of lazy values (function representation)
        if self.type == XValue.TIME_DEPENDENT and self.context.time() != self.time:
            self.rval = self.fval(self.context.time()) #evaluated only if is not cached
            self.time = self.context.time()
        elif self.type == XValue.RANDOM and self.rval is None: 
            self.rval = self.fval()       #evaluated only once in the scope (for the first access)
    
    
    @staticmethod
    def isPrimitiveType(obj):
        return isinstance(obj, numbers.Real) or isinstance(obj, bool) or isinstance(obj, str)
    
    distDict = dict(
        normal = (random.normalvariate, ("mu", 0.0), ("sigma", 1.0)),
        pnormal = (lambda *param: max(random.normalvariate(*param), 0), ("mu", 0.0), ("sigma", 1.0)),
        uniform = (random.uniform, ("min", 0.0), ("max", 1.0)),
        triangular = (random.triangular, ("low", 0.0), ("high", 1.0), ("mode", 1.0)),
        beta = (random.betavariate, ("alpha", 0.0), ("beta", 1.0)),
        gamma = (random.gammavariate, ("alpha", 1.0), ("beta", 1.0)),
        lognormal = (random.lognormvariate, ("mu", 0.0), ("sigma", 1.0)),
        vonmises = (random.vonmisesvariate, ("mu", 0.0), ("kappa", 1.0)),
        pareto = (random.paretovariate, ("alpha", 0.0)),
        weibull = (random.weibullvariate, ("alpha", 0.0), ("beta", 1.0)),
        exponential = (random.expovariate, ("lambda", 1.0) )
    )

    distSet = frozenset(distDict.keys())
    
    @staticmethod
    def fromJson(obj):
        if XValue.isPrimitiveType(obj):
            return XValue(obj)        
        
        expectedKeys = {"context", "value"} | XValue.distSet
        usedKeys = set(obj.keys())
        
        if not usedKeys.issubset(expectedKeys):
            raise SimDslError(
                "Unsupported keys in JSON representation of X-value. Supported: {0}, Used: {1}",
                expectedKeys, usedKeys)
        
        if "value" in obj:
            return XValue(obj["value"])
        
        objDist = usedKeys.intersection(XValue.distSet)
        
        if len(objDist) == 1:
            dist = objDist.pop()
            parObject = obj[dist]
            
            validNames = { name for name, _ in XValue.distDict[dist][1:] }
            usedNames = set(parObject.keys())
            
            if not usedNames.issubset(validNames):
                raise  SimDslError("Undefined distribution parameters. Expected: {0}, Used : {1}",
                                       validNames, usedNames)
            
            params = [ parObject[parName] if parName in parObject else default
                        for parName, default in XValue.distDict[dist][1:] ]
            return XValue(lambda : XValue.distDict[dist][0](*params))
        
        assert False, "Invalid JSON parsing"
                
    
    def __float__(self):
        self._eval()
        assert isinstance(self.rval, numbers.Real)
        return float(self.rval)
    
    def __int__(self): #the integral value is preserved
        self._eval()
        assert isinstance(self.rval, numbers.Integral)
        return int(self.rval)
    
    def __bool__(self):
        self._eval()
        assert isinstance(self.rval, bool)
        return bool(self.rval)
        
    def __str__(self):
        self._eval()
        assert isinstance(self.rval, str)
        return str(self.rval)
    
    def __repr__(self):
        return str(self.rval)
    
    
    def _binaryOperation(self, x, op, reversedOperands): #general code for binary operation
        assert isinstance(self.rval, numbers.Real)
        self._eval()
        if isinstance(x, numbers.Real):
            return op(self.rval,  x) if not reversedOperands else op(x, self.rval)
        elif isinstance(x, XValue):
            x._eval()
            return op(self.rval, x.rval) if not reversedOperands else op(x.rval, self.rval)
        else:
            raise TypeError("invalid type of operand in binary operation")
        
    def _unaryOperation(self, op): #unary operators are simple (no any conversions)
        assert isinstance(self.rval, numbers.Real)
        self._eval()
        return op(self.rval)
        
    def __add__(self, x): #normal add (left operator is x-value)
        return self._binaryOperation(x, operator.add, False)
        
    def __radd__(self, x):  #reverse add (left operator is no x-value)
        return self._binaryOperation(x, operator.add, True)
        
    def __mul__(self, x):
        return self._binaryOperation(x, operator.mul, False)
        
    def __rmul__(self, x):
        return self._binaryOperation(x, operator.mul, True)
        
    def __sub__(self, x):
        return self._binaryOperation(x, operator.sub, False)
        
    def __rsub__(self, x):
        return self._binaryOperation(x, operator.sub, True)
        
    def __truediv__(self, x):
        return self._binaryOperation(x, operator.truediv, False)
        
    def __rtruediv__(self, x):
        return self._binaryOperation(x, operator.truediv, True)
        
    def __neg__(self):
        return self._unaryOperation(operator.neg)
        
    def __abs__(self):
        return self._unaryOperation(operator.abs)
        
    def __pos__(self):
        return self._unaryOperation(operator.pos)

class XAttribute:
    def __init__(self, name, xvalue, contextTag):
        self.name = name
        self.xvalue = xvalue
        self.contextTag = contextTag
        
    def get(self, contextHelper):
        context = contextHelper.getContext(self.contextTag)
        self.xvalue.setContext(context)
        return self.xvalue
    
    @staticmethod
    def yamlToJson(text):
        text = text.strip()
        if re.match(r"\w+\s*:", text):
            text = re.sub(r"(\w+)\s*:", r'"\1":', text)
            return "{" + text + "}"
        if re.match(r"^([a-z_][a-z0-9_]*\.)*[a-z_][a-z0-9_]*$", text):
            return '"{0}"'.format(text)
        return text
        
        
    @staticmethod
    def fromJsonString(name, jsonString, parameterDict = None):
        if parameterDict is not None:
            jsonString = string.Template(jsonString).substitute(parameterDict)
        obj = json.loads(XAttribute.yamlToJson(jsonString))
        contextTag = None if not isinstance(obj, dict) or "context" not in obj else obj["context"]
        return XAttribute(name, XValue.fromJson(obj), contextTag)
    
    def __str__(self):
        return fmt("[ value: {0} #(context: {1}|nc)]", repr(self.xvalue), self.contextTag)


class FullId:
    def __init__(self, typeId, instanceId):
        self.typeId = typeId
        self.instanceId = instanceId
        
    def match(self, compId):
        if self.typeId == compId.typeId and self.instanceId == compId.instanceId:
            return True
        if compId.instanceId == "" and self.typeId == compId.typeId:
            return True
        return False

    def __str__(self):
        return fmt("{0}#(:{1})", self.typeId, self.instanceId)

class Node:
    def __init__(self, typeTag):
        self.typeTag = typeTag
        self.attributes =  {}
        self.subnodes = []
        self.externalNodes = {}
        
    def addAttribute(self, attribute):
        assert attribute.name not in self.attributes
        self.attributes[attribute.name] = attribute
        
    def addSubNode(self, node):
        self.subnodes.append(node)
        
    @property    
    def fullId(self):
        instanceId = str(self.attributes["id"].xvalue) if "id" in self.attributes else ""
        return FullId(self.typeTag, instanceId)
    
    def merge(self, mergedict, overwrite):
        for key in mergedict.keys():
            if self.fullId.match(key):
                nodedict = mergedict[key]
                if overwrite:
                    self.attributes.update(nodedict)
                else:
                    for pkey in nodedict.keys():
                        self.attributes.setdefault(pkey, nodedict[pkey])

        for subnode in self.subnodes:
            subnode.merge(mergedict, overwrite)
        
    def __str__(self):
        return (fmt("<{0}#( attrib:{1})#( elements: {2})#( exNodes: {3})>",
                        self.typeTag,
                        { key: str(value) for key, value in self.attributes.items()},
                        [ str(node) for node in self.subnodes],
                        { key : str(value) for key, value in self.externalNodes.items()}
                        ))
        

class QName:
    def __init__(self, name, namespace = ""):
        match = re.match("^{([^}]*)}([A-Za-z_-][A-Za-z0-9_-]*)$", name)
        if match:
            self.namespace = match.group(1)
            self.localname = match.group(2)
        else:
            self.namespace = namespace
            self.localname = name
    
    def __iter__(self):
        yield self.namespace
        yield self.localname
        
    def __str__(self):
        if self.namespace == "":
            return self.localname
        else:
            return "{" + self.namespace + "}" + self.localname
        
    def hasNamespace(self, namespace):
        return self.namespace == namespace
        

class EtreeBuilder:
    operatorNS = "http://jf.cz/ns/simdsl/operators"
    
    @staticmethod    
    def build(url):
        element, base = EtreeBuilder.openAndParseUrl(EtreeBuilder.normalizeUrl(url))
        if element is None:
            raise SimDslError("Invalid XML on URL {0}", EtreeBuilder.normalizeUrl(url))
        return EtreeBuilder._createNode(element, base)
    
    @staticmethod
    def _createNode(element, base):
        node = Node(element.tag)
        operators = []
        for key, value in element.attrib.items():
            qname = QName(key)
            if qname.hasNamespace(EtreeBuilder.operatorNS):
                operators.append((qname.localname, value))
            else:
                node.addAttribute(XAttribute.fromJsonString(key, value))
    
        node.subnodes = [EtreeBuilder._createNode(subelement, base) for subelement in element]
        
        for opcode, url in operators:
            subBuilder = EtreeBuilder()
            target = urljoin(base, url)
            externalNode = subBuilder.build(target)
            if opcode == "INSERT":
                if node.subnodes:
                    raise SimDslError("Insertion into nonempty node")
                node.subnodes = externalNode.subnodes 
            elif opcode == "APPEND":
                node.subnodes.extends(externalNode.subnodes)
            elif opcode == "INJECT_ATTRS":
                node.merge({mnode.fullId : mnode.attributes
                                    for mnode in externalNode.subnodes}, overwrite = True)
            elif opcode == "DEFAULT_ATTRS":
                node.merge({mnode.fullId : mnode.attributes
                                    for mnode in externalNode.subnodes}, overwrite = False)
            elif opcode == "SKIP_NODES":
                node.subnodes = []
            else:
                node.externalNodes[opcode]=externalNode
        print(node.fullId)
        return node
       
    @staticmethod
    def openAndParseUrl(url):
        with urlopen(url) as response:
            root = ET.parse(response)
            baseurl = response.geturl()
            urlparts = urlparse(url)
            if urlparts.fragment  ==  "":
                rootElement = root.getroot()
            else:
                rootElement = root.find(urlparts.fragment)
        return (rootElement, baseurl)        
    
    
    @staticmethod    
    def normalizeUrl(urlString):
        url = urlparse(urlString)

        if url.scheme in ["file", ""]:
            scheme = "file"
            path = (url.path if url.path.startswith("/") else os.getcwd() + "/" + url.path)
        else:
            scheme = url.scheme
            path = url.path
        return urlunparse((scheme, url.netloc, path, "", "", url.fragment))
        

print(EtreeBuilder.build("XML/test.xml#a"))

#context = XValueContext()        
#p = XAttribute.fromJsonString("velocity", 'pnormal:{mu:$mu, sigma:100}', dict(mu=10))
#for i in range(10):
#    with context:
#        print(float(p.get(DummyXValueHelper(context))))

