import weakref
import numbers
import inspect
import operator
import random

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
        
if __name__ == '__main__':
    context = XValueContext(lambda: 5)
    time = context.t        
    print(time)



    



