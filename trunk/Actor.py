from XValue import *

class Actor:
    def __init__(self, transaction):
        self.xcontext = XValueContext()
        self.transaction = transaction
        self.simulation = self.transaction.simulation
        
class E_car(Actor):
    def __init__(self, transaction):
        super().__init__(transaction)

