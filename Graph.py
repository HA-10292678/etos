#!/usr/bin/env python3

def toFunction(value):
    return value if callable(value) else lambda t=None: value #per key closure

class SGDEntity:
    def __init__(self, **kwargs):
        self.attrs = {key : toFunction(value) for key, value in kwargs.items()}
        if "id" not in self.attrs:
            self.addAttribute("id", self.getDefaultId())
                
    @classmethod
    def getDefaultId(cls):
        cls.counter += 1
        return cls.counter
        
    def addAttribute(self, key, value):
        if key in self.attrs:
            raise AttributeError("Unambigous attribute")
        self.attrs[key] = value if callable(value) else lambda t=None: value
            
    def __getitem__(self, key):
        return self.attrs[key]
    
    def __getattr__(self, key):
        return self.attrs[key]
    
    def get(self, key, default):
        return self.attrs.get(key, default)

class SGDNode(SGDEntity):
    counter = 0
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.edges = []
        
    def edgeTo(self, target, **kwargs):
        edge = SGDEdge(self, target, **kwargs)
        self.edges.append(edge)
        return edge
    
    def bidiEdgesTo(self, target, **kwargs):
        edge = SGDEdge(self, target, **kwargs)
        self.edges.append(edge)
        backEdge = SGDEdge(target, self, **kwargs)
        target.edges.append(backEdge)
        return (edge, backEdge)   #returns pair of edges       
    
    def __str__(self):
        return "Node:{0}".format(self.attrs["id"]())

class SGDEdge(SGDEntity):
    counter = 0
    
    def __init__(self, start, target, **kwargs):
        super().__init__(**kwargs)
        self.start = start
        self.target = target

    def __str__(self):
        return "{0}->{1}".format(self.start.id(), self.target.id())

class DiGraph:
    def __init__(self, *args):
        self.nodes = list(args)
    
    def addNode(self, node):
        self.nodes.append(node)
    
    def ifTrueFilter(self, attrName):
        return [node for node in self.nodes if node.get(attrName, False)]
        
    def __len__(self):
        return len(self.nodes)

n1 = SGDNode(id="mesto", delay=10, fuel=True)
n2 = SGDNode(delay=20, fuel=True)

graph = DiGraph(n1, n2)

print( n1.edgeTo(n2, delay=50) )
print(n1.delay())

print (",".join(str(node) for node in graph.ifTrueFilter("fuel")))
