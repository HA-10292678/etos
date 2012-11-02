#!/usr/bin/env python3

import collections

class Dumper():
    def __init__(self):
        self.dumped = set()
    def dump(self, obj):
        if isinstance(obj, dict):
            return {key : self.dump(value) for key,value in obj.items()}
        if isinstance(obj, list):
            return [self.dump(item) for item in obj]
        if hasattr(obj, "__float__"):
            return float(obj)
        if hasattr(obj, "__str__"):
            return "(" + str(obj) + ")"
        if hasattr(obj, "__dict__") and isinstance(obj, collections.Hashable):
            if obj in self.dumped:
                return "<r>"
            self.dumped.add(obj)
            return {key : self.dump(value) for key,value in vars(obj).items() }
        else:
            return repr(obj)


