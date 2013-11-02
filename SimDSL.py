#!/usr/bin/env python3

import numbers
import inspect
import operator
import random
import TimeUtil

import xml.etree.ElementTree as ET
import pprint
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.request import urlopen
import os

##########################################################
# modul XVAlue (převzato a upraveno)
########################################################## 

class XValueHelper:
    ENTITY_CONTEXT = 0
    TRANSACTION_CONTEXT = 1
    ACTOR_CONTEXT = 2
    SIMULATION_CONTEXT = 3
    
    tagNames = {"entity" : ENTITY_CONTEXT, "transaction" : TRANSACTION_CONTEXT,
                "actor" : ACTOR_CONTEXT, "simulation" : SIMULATION_CONTEXT}
    
    def __init__(self, entity, stdContextType = ENTITY_CONTEXT):
        transaction = entity.transaction
        actorContext = transaction.actor.xcontext
        
        self.contexts = (entity.xcontext, transaction.xcontext,
                         actorContext,transaction.simulation.xcontext)
        self.parameterProvider = transaction.simulation
        self.stdContext = self.contexts[stdContextType]
        

    def getContext(self, contextTag):
        return self.contexts[self.tagNames[contextTag]]
    
    
    def getParameter(self, id):
        xvalue = self.parameterProvider.getParameter(id)
        return xvalue

def arity(func):
    return len(inspect.getargspec(func)[0])

class XValueType:
    FIXED = 0
    RANDOM = 1
    TIME_DEPENDENT = 2

class XValue:
    def __init__(self, value):
        assert value is not None #null (undefined) values are not supported
        self.context = None
        if isinstance(value, numbers.Real) or isinstance(value, bool):
            self.type = XValueType.FIXED #fixed integral, float number or bool
            self.fval = None
            self.rval = value
        elif callable(value) and arity(value) == 0: #parameterless generator
            self.type = XValueType.RANDOM
            self.fval = value
            self.rval = None
        elif callable(value) and arity(value) == 1: #function of context time
            self.type = XValueType.TIME_DEPENDENT
            self.fval = value
            self.rval = None
        else:
            raise TypeError("unsupported value type")
        self.time = None
    
    def setContext(self, context):
        self.context =  context
        self.context.addValue(self)
    
    def reset(self): #reset random value in the begining of new scope
        if self.type == XValueType.RANDOM:
            self.rval = None
               
    def _eval(self): #evaluating of lazy values (function representation)
        if self.type == XValueType.TIME_DEPENDENT and self.context.time() != self.time:
            self.rval = self.fval(self.context.time()) #evaluated only if is not cached
            self.time = self.context.time()
        elif self.type == XValueType.RANDOM and self.rval is None: 
            self.rval = self.fval()       #evaluated only once in the scope (for the first access)
    
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
        return str(float(self.rval))
    
    def __repr__(self):
        return repr(vars(self))
    
        
    
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
    

##########################################################
# modul SIM-DSL
########################################################## 

class BaseXAttribute:
    def __init__(self, name, contextTag):
        self.name = name
        self.contextTag = contextTag
    
    def isCompound(self):
        raise NotImplementedError("Abstract method")

class XAttribute(BaseXAttribute):
    def __init__(self, name, *, contextTag = None, xvalue = None, parameterId = None):
        super().__init__(name, contextTag)
        self.xvalue = xvalue
        self.parameterId = parameterId
        
    def get(self, contextHelper):
        context = (contextHelper.stdContext if self.contextTag is None
                    else contextHelper.getContext(contextHelper.fromAttribName(self.contextTag)))
    
        if self.parameterId is not None:
            self.xvalue = contextHelper.getParameter(self.parameterId)
            self.parameterId = None
        self.xvalue.setContext(context)
        return self.xvalue
    
    def isCompound(self):
        return False
    
    def __repr__(self):
        return "[XAttribute name:{0}, contextTag:{1}, value:{2}]".format(
            self.name, self.contextTag,
            repr(self.xvalue) if self.xvalue is not None else "$" + self.parameterId)


class CompoundXAttribute:
    def __init__(self, name, *, contextTag = None ):
        super().__init__(name, contextTag)    
        self.attribs = {}
    
    def addAttribute(self, name, attribute):
        assert name not in self.attribs
        if attribute.contextTag is None: #partial attribute inherits parent context
            attribute.context = self.contextTag
        self.attribs[name] = attribute
        
    def isCompound(self):
        return True
        
    def get(self, itemName, contextHelper):
        return self.attribs[itemName].get(contextHelper)

class Node:
    def __init__(self, nodeType, nodeId):
        self.nodeType = nodeType
        self.nodeId = nodeId
        self.xattrs = {}
        self.strattrs = {}
        self.nodes = []      
       
    def addNode(self, node):
        self.nodes.append(node)
        
    def addXAttribute(self, attribute):
        if attribute.name in self.xattrs:
            raise KeyError("The unambiguous x-attribute {0}".format(attribute.name))
        self.xattrs[attribute.name] = attribute
        
    def addStrAttribute(self, name, value):
        if name in self.strattrs:
            raise KeyError("The unambiguous string attribute {0}".format(name))
        self.strattrs[name] = value
       
    def getXAttribute(self, attrname, contextHelper, default = None):
        if attrname in self.xattrs:
            return self.xattrs[attrname].get(contextHelper)
        else:
            if default is None:
                raise KeyError("Undefined x-attribute {0}".format(attrname))
            return default
        
    def getStringAttribute(self, attrname, default=None):
        if attrname in self.strattrs:
            return self.strattrs[attrname]
        else:
            if default is None:
                raise KeyError("Undefined string attribute {0}".format(attrname))
            return default            
    
    
    def __iter__(self):
        return iter(self.nodes)
    
    
##########################################################
# modul XML builder
##########################################################    
    
def parseText(text):
    text = text.lower()
    if text == "":
        raise InvalidXMLException("empty attribute value")
    if text in ["true", "false"]:
        return XValue(text == "true")
    if ":" in text:
        return float(TimeUtil.strdt(text))
    if(all(c in "0123456789" for c in text)):
        return XValue(int(text))
    else:
        return XValue(float(text))
    
def number(text):
    if ":" in text:
        return float(TimeUtil.strdt(text))
    else:
        return float(text)

def randomXValue(tag, params):
    if tag == "normal":
        mu = number(params.get("mu", 0.0))
        sigma = number(params.get("sigma", 1.0))
        return XValue(lambda: random.normalvariate(mu, sigma))
    if tag == "pnormal":
        mu = number(params.get("mu", 0.0))
        sigma = number(params.get("sigma", 1.0))
        return XValue(lambda: max(random.normalvariate(mu, sigma), 0.0))        
    elif tag == "uniform":
        mn = number(params.get("min", 0.0)) 
        mx = number(params.get("max", 1.0))
        return XValue(lambda: random.uniform(mn, mx))
    elif tag == "triangular":
        low = number(params.get("low", 0.0)) 
        high = number(params.get("high", 1.0))
        mode = number(params.get("mode", 1.0))
        return XValue(lambda: random.triangular(low, high, mode))
    elif tag == "beta":
        alpha = number(params.get("alpha", 0.0)) 
        beta = number(params.get("beta", 1.0))
        return XValue(lambda: random.betavariate(alpha, beta))
    elif tag == "gamma":
        alpha = number(params.get("alpha", 0.0)) 
        beta = number(params.get("beta", 1.0))
        return XValue(lambda: random.gammavariate(alpha, beta))
    elif tag == "lognormal":
        mu = number(params.get("mu", 0.0))
        sigma = number(params.get("sigma", 1.0))
        return XValue(lambda: random.lognormvariate(mu, sigma))
    elif tag == "vonmises":
        mu = number(params.get("mu", 0.0))
        kappa = number(params.get("kappa", 1.0))
        return XValue(lambda: random.vonmisesvariate(mu, kappa))
    elif tag == "pareto":
        alpha = number(params.get("alpha", 0.0))
        return XValue(lambda: random.paretovariate(alpha))
    elif tag == "weibull":
        alpha = number(params.get("alpha", 0.0)) 
        beta = number(params.get("beta", 1.0))
        return XValue(lambda: random.weibullvariate(alpha, beta))
    elif tag == "exponential":
        lamda = number(params.get("lambda", 1.0))
        return XValue(lambda: random.expovariate(lamda))
    else:
        raise InvalidXMLException("unsupported attribute value")
    
    
class UrlPath:
    def __init__(self, url):
      if url is not None:  
        self.url = urlparse(url)
      else:
        self.url = urlparse("")
      
    def getPath(self, url):
        target = urlparse(url)
        
        targetPath = (target.path if target.path == "" or target.path.startswith("/")
                        else os.getcwd() + "/" + target.path) 
        fromUrlPart = urlunparse((self.url.scheme or "file", self.url.netloc, self.url.path,
                                  "", "", ""))
        toUrlPart = urlunparse((target.scheme or "file", target.netloc, targetPath, 
                                  "", "", ""))
        diffUrl = urljoin(fromUrlPart, toUrlPart)
        diffUrl = None if diffUrl == fromUrlPart else diffUrl
        return (diffUrl, target.fragment)
    

    
class EtreeBuilder:
    def __init__(self, * , root, baseUrl=None, strict=False, nodeIds=None):
        self.baseUrl = UrlPath(baseUrl)
        self.strict = strict
        self.namespace = "{http://ki.ujep.cz/ns/sim-dsl}" if strict else ""
        self.nodeIds = set(nodeIds) if nodeIds is not None else set()
        self.root = root
        
    def ns(self, localname):
        return self.namespace + localname
    
    def _processAttribute(self, node, name, value):
        if name == self.ns("aContext"):
            self._mergeAttributes(node, value)
        elif name == self.ns("nContext"):
            self._mergeNodes(node, value)
        elif name.startswith("{") or (not self.strict and name == "id"):
            return
        elif value.startswith("#"):
            node.addXAttribute(XAttribute(name, xvalue=parseText(value[1:])))
        elif value.startswith("$"):
            node.addXAttribute(XAttribute(name, parameterId=value[1:]))
        else:
            node.addStrAttribute(name, value)
            
    def _processElement(self, node, subElement):
        if (subElement.attrib.get(self.ns("attribute"), False) or
            (not self.strict and subElement.tag not in self.nodeIds)): #subelement is x-attribute
            name = subElement.tag
            text = subElement.text.strip() if subElement.text is not None else ""
            contextTag = subElement.attrib.get(self.ns("context"), None)
            if len(subElement):  #random x-value
                assert len(subElement) == 1
                rvalue = randomXValue(subElement[0].tag, subElement[0].attrib)
                node.addXAttribute(XAttribute(name, contextTag = contextTag, xvalue = rvalue))
            elif text.startswith("$"):
                node.addXAttribute(XAttribute(name, contextTag = contextTag,
                                              parameterId=text[1:]))
            else:
                node.addXAttribute(XAttribute(name, contextTag = contextTag,
                                           xvalue = parseText(text)))   
        else: #subelement is node
            node.addNode(self._buildElement(subElement))
            
    def _mergeAttributes(self, node, path):
        url, xpath = self.baseUrl.getPath(path)
        exNode = None
        if url is None:
            exNode = self.build(xpath)
        else:
            eXnode = self._getExternalNode(url, xpath)
        node.xattrs.update(exNode.xattrs)
        node.strattrs.update(exNode.strattrs)
        
    def _mergeNodes(self, node, path):
        url, xpath = self.baseUrl.getPath(path)
        exNode = None
        if url is None:
            exNode = self.build(xpath)
        else:
            eXnode = self._getExternalNode(url, xpath)
        node.nodes.extend(exNode.nodes)
    
        
    def _getExternalNode(self, url, xpath):
        stream = urlopen(url)
        document = ET.parse(stream)
        builder = EtreeBuilder(root=root, baseUrl=url, strict=self.strict, nodeIds = self.nodeIds)
        node = builder.build(xpath)
        return node
    
    def _buildElement(self, element):
        node = Node(element.tag, element.attrib.get(self.ns("id"), None))
        for name, value in element.attrib.items():
            self._processAttribute(node, name, value)
                 
        for subElement in element:
            self._processElement(node, subElement)
                
        return node
    
        
    def build(self, xpath = "."):
        element = self.root.find(xpath)
        return self._buildElement(element)
    

##########################################################
# testovací kód
########################################################## 
        
eb = EtreeBuilder(root=ET.fromstring("""
<root>                                   
<pokus id="pokus-id" at1="string" at2="#5" aContext="#test">
    <at3 context="context">6</at3>
    <at4><normal mu="6" sigma="2.5"/></at4>
    <subnode>
    </subnode>
</pokus>
<test>
    <at5>8</at5>
</test>
</root>
"""), nodeIds=["subnode"])

node = eb.build("./pokus")

pprint.pprint(vars(node))

    
    
    
