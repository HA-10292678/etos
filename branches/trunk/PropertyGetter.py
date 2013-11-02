#!/usr/bin/env python3
import re


class Property:
    def __init__(self, propSpec):
        if not re.match(r"^[etosa]\.\w+", propSpec):
            raise RuntimeError("invalid property specifier")
        self.locator, self.propName = propSpec.split(".")
        
    def get(self, transaction, entity):
        obj = None
        if self.locator == "a":
            obj = transaction.actor
            if(hasattr(obj, self.propName)):
               return getattr(obj, self.propName)
            else:
              return obj.props[self.propName]
        if self.locator == "t":
            obj = transaction
        elif self.locator == "s":
            obj = transaction.simulation
        elif self.locator == "e":
            obj = entity
        elif self.locator == "o":
            obj = entity.sharedObject
        return getattr(obj, self.propName)

    def set(self, transaction, entity, value):
        obj = None
        if self.locator == "a":
            obj = transaction.actor
            if(hasattr(obj, self.propName)):
                setattr(obj, self.propName, value)
            else:
                obj.props[self.propName] = value
            return
        if self.locator == "t":
            obj = transaction
        elif self.locator == "s":
            obj = transaction.simulation
        elif self.locator == "e":
            obj = entity
        elif self.locator == "o":
            obj = entity.sharedObject
        setattr(obj, self.propName, value)
