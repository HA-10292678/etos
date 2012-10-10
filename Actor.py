from XValue import *

class Actor:
    def __init__(self, simulation, xmlSource, extraProperties = False):
        self.xcontext = XValueContext(lambda: self.simulation.now() - self.startTime)
        self.simulation = simulation
        self.xmlSource = xmlSource
        self.startTime = self.simulation.now()
        self.props = {}
        if extraProperties:
            for element in xmlSource:
                tag = element.tag
                self.props[tag] = getXValue(xmlSource, tag, self.xcontext)
        
    def __str__(self):
        return ",".join(self.props.keys())

        
        



