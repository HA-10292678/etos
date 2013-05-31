#!/usr/bin/env python3

import subprocess

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

class SGDDistance:
    def __init__(self, distance, previous):
        self.distance = distance
        self.previous = previous

class SGDPath:
    def __init__(self, startNode, finalNode, distance, path):
        self.startNode = startNode
        self.finalNode = finalNode
        self.distance = distance
        self.path = path

    def __str__(self):
        pathlist = []
        pathlist.append(str(self.distance))
        pathlist.append(" = ")
        for node in self.path:
            pathlist.append(node.id())
            pathlist.append(" -> ")
        pathlist.append(self.startNode.id())
        pathlist.reverse()
        return "".join(pathlist)

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
        attrlist = []
        for key, value in self.attrs.items():
            attrlist.append(key)
            attrlist.append(": ")
            attrlist.append(str(value()))
            attrlist.append("\\n")
        return "{0} [label=\"{1}\"]".format(self.id(),  "".join(attrlist))

class SGDEdge(SGDEntity):
    counter = 0
    def __init__(self, start, target, **kwargs):
        super().__init__(**kwargs)
        self.start = start
        self.target = target

    def __str__(self):
        attrlist = []
        for key, value in self.attrs.items():
            attrlist.append(key)
            attrlist.append(": ")
            attrlist.append(str(value()))
            attrlist.append("\\n")
        return "{0} -> {1} [label=\"{2}\"]".format(self.start.id(), self.target.id(), "".join(attrlist))

class DiGraph:
    def __init__(self, *args):
        self.nodes = list(args)
    
    def addNode(self, node):
        self.nodes.append(node)
    
    def ifTrueFilter(self, attrName):
        return [node for node in self.nodes if node.get(attrName, False)]
        
    def __len__(self):
        return len(self.nodes)
    
    def getDistances(self, startNode, attr):
        distances = {}
        queue = []
        
        for node in self.nodes:
            if (node != startNode):
                distances[node] = SGDDistance(float('inf'), None)
            else:
                distances[node] = SGDDistance(0, None)
            queue.append(node)
        
        while (len(queue) > 0):
            minimum = distances[min(queue, key=lambda node: distances[node].distance)].distance
            if (minimum == float('inf')):
                break # discontinuous graph
            for node in [node for node in queue if distances[node].distance == minimum]:
                queue.remove(node)
                for edge in node.edges:
                    # TODO: capacity of edges
                    alt = distances[edge.start].distance + edge.attrs[attr]() + edge.start.attrs[attr]()
                    if (distances[edge.target].distance > alt):
                        distances[edge.target] = SGDDistance(alt, node)
        
        return distances
    
    def processDistance(self, distances, finalNode):
        path = []
        temp = finalNode
        while (temp != startNode):
            if (temp == None):
                break # path does not exist
            path.append(temp)
            temp = distances[temp].previous
        return path
    
    def getPaths(self, startNode, attr, nodeFilter=lambda node: True):
        distances = self.getDistances(startNode, attr)
        paths = []
        for finalNode in distances.keys():
            if nodeFilter(finalNode):
                paths.append(SGDPath(startNode, finalNode, distances[finalNode].distance, self.processDistance(distances, finalNode)))
        return paths
    
    def toDot(self):
        code = []
        code.append("digraph {\n")
        for node in self.nodes:
            code.append("    ")
            code.append(str(node))
            code.append("\n")
        for node in self.nodes:
            for edge in node.edges:
                code.append("    ")
                code.append(str(edge))
                code.append("\n")
        code.append("}\n")
        return ''.join(code)

nA = SGDNode(id="A", delay=0, final=0)
nB = SGDNode(id="B", delay=0, final=0)
nC = SGDNode(id="C", delay=0, final=0)
nD = SGDNode(id="D", delay=0, final=0)
nE = SGDNode(id="E", delay=0, final=1)
nF = SGDNode(id="F", delay=0, final=1)
nG = SGDNode(id="G", delay=0, final=1)
nX = SGDNode(id="X", delay=0, final=0)

graph = DiGraph(nA, nB, nC, nD, nE, nF, nG, nX)

nA.edgeTo(nB, delay=1)
nA.edgeTo(nC, delay=3)
nA.edgeTo(nF, delay=8)
nB.edgeTo(nD, delay=4)
nB.edgeTo(nF, delay=9)
nC.edgeTo(nE, delay=1)
nC.edgeTo(nF, delay=2)
nD.edgeTo(nG, delay=2)
nD.edgeTo(nF, delay=5)
nE.bidiEdgesTo(nF, delay=1)
nG.bidiEdgesTo(nF, delay=1)

# z A do A je 0
# z A do B je 1
# z A do C je 3
# z A do D je 5
# z A do E je 4
# z A do F je 5
# z A do G je 6

print(graph.toDot())

startNode = nA
for path in graph.getPaths(startNode, "delay", lambda node: node.final()):
    print(str(path))
print()
for path in graph.getPaths(startNode, "delay"):
    print(str(path))


