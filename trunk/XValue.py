import weakref
import numbers
import inspect
import operator
import random
import TimeUtil

class InvalidXMLException(Exception):
    "invalid structure in XML input data"
    def __init__(self, msg):
        super().__init__(msg)

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
    def t(self):  #return auxiliary x-value represented context time
        return XValue(lambda t:t, self)
    
def arity(func):
    return len(inspect.getargspec(func)[0])

class XValueType:
    FIXED = 0
    RANDOM = 1
    TIME_DEPENDENT = 2

class XValue:
    def __init__(self, value, context):
        assert value is not None #null (undefined) values are not supported 
        self.context =  context
        self.context.addValue(self)
        if isinstance(value, numbers.Real):
            self.type = XValueType.FIXED #fixed itegral or float number
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
        
    def __str__(self):
        self._eval()
        return str(float(self.rval))
        
    
    def _binaryOperation(self, x, op, reversedOperands): #general code for binary operation
        self._eval()
        if isinstance(x, numbers.Real):
            return op(self.rval,  x) if not reversedOperands else op(x, self.rval)
        elif isinstance(x, XValue):
            x._eval()
            return op(self.rval, x.rval) if not reversedOperands else op(x.rval, self.rval)
        else:
            raise TypeError("invalid type of operand in binary operation")
        
    def _unaryOperation(self, op): #unary operators are simple (no any conversions)
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
    

def number(text, keepInt = False):
    if text == "":
        raise InvalidXMLException("empty attribute value")
    if ":" in text:
        return float(TimeUtil.strdt(text))
    text = text.strip()
    if not keepInt:
        return float(text)
    if(all(c in "0123456789" for c in text)):
        return int(text)
    else:
        return float(text)
    
    
def getXValue(xmlSource, tag, context, default = None):
    node = xmlSource.findNode(tag)
    if node is None:
        if default is not None:
            return XValue(default)
        raise InvalidXMLException("undefined attribute {0}".format(tag))
    subNode = node.find("*")
    if subNode is None:
        ntext = node.text 
        return number(ntext, keepInt=True)
    if subNode.tag == "normal":
        mu = number(subNode.get("mu", 0.0))
        sigma = number(subNode.get("sigma", 1.0))
        return XValue(lambda: random.normalvariate(mu, sigma), context)
    if subNode.tag == "pnormal":
        mu = number(subNode.get("mu", 0.0))
        sigma = number(subNode.get("sigma", 1.0))
        return XValue(lambda: max(random.normalvariate(mu, sigma), 0.0), context)        
    elif subNode.tag == "uniform":
        mn = number(subNode.get("min", 0.0)) 
        mx = number(subNode.get("max", 1.0))
        return XValue(lambda: random.uniform(mn, mx), context)
    elif subNode.tag == "triangular":
        low = number(subNode.get("low", 0.0)) 
        high = number(subNode.get("high", 1.0))
        mode = number(subNode.get("mode", 1.0))
        return XValue(lambda: random.triangular(low, high, mode), context)
    elif subNode.tag == "beta":
        alpha = number(subNode.get("alpha", 0.0)) 
        beta = number(subNode.get("beta", 1.0))
        return XValue(lambda: random.betavariate(alpha, beta), context)
    elif subNode.tag == "gamma":
        alpha = number(subNode.get("alpha", 0.0)) 
        beta = number(subNode.get("beta", 1.0))
        return XValue(lambda: random.gammavariate(alpha, beta), context)
    elif subNode.tag == "lognormal":
        mu = number(subNode.get("mu", 0.0))
        sigma = number(subNode.get("sigma", 1.0))
        return XValue(lambda: random.lognormvariate(mu, sigma), context)
    elif subNode.tag == "vonmises":
        mu = number(subNode.get("mu", 0.0))
        kappa = number(subNode.get("kappa", 1.0))
        return XValue(lambda: random.vonmisesvariate(mu, kappa), context)
    elif subNode.tag == "pareto":
        alpha = number(subNode.get("alpha", 0.0))
        return XValue(lambda: random.paretovariate(alpha), context)
    elif subNode.tag == "weibull":
        alpha = number(subNode.get("alpha", 0.0)) 
        beta = number(subNode.get("beta", 1.0))
        return XValue(lambda: random.weibullvariate(alpha, beta), context)
    elif subNode.tag == "exponential":
        lamda = number(subNode.get("lambda", 1.0))
        return XValue(lambda: random.expovariate(lamda), context)
    else:
        raise InvalidXMLException("unsupported attribute value")    
        




    



