#!/usr/bin/env python3
import re
from functools import total_ordering

def dtstr(sec):
    return str(DayTime(seconds=sec))
    
def strdt(s):
    return DayTime.fromString(s)

@total_ordering
class DayTime:
    rexp = r"^\s*(?:(\d+)\s*[dD]\s*)?(\d+)\s*:\s*(\d+)(?:\s*:\s*(\d+(\.\d*)?))?\s*$"
    subrexp = r"(?:(\d+)[dD])?(\d+):(\d+)(?::(\d+(\.\d*)?))?"
    def __init__(self, *, days = 0, hours = 0, minutes = 0, seconds = 0):
            self.t = days * 60 * 60 * 24 + hours * 60 * 60 + minutes * 60 + seconds
            
    @staticmethod
    def matchString(s):
        match = re.match(DayTime.rexp, s)
        return match
        
        
    @staticmethod
    def substituteDayTimes(s):
        return re.sub(DayTime.subrexp, lambda match: str(DayTime._fromMatch(match).totalSecond) , s)
        
    @staticmethod
    def _fromMatch(match):
        if not match:
            raise Exception("invalid daytime format")
        d = float(match.group(1)) if match.group(1) is not None else 0
        h = float(match.group(2))
        m = float(match.group(3))
        s = float(match.group(4)) if match.group(4) is not None else 0
        return DayTime(days=d, hours=h, minutes=m, seconds=s)
        
    @staticmethod
    def fromString(s):
        match = DayTime.matchString(s)
        return DayTime._fromMatch(match)      
            
        
    @property
    def totalSecond(self):
        return self.t

    @property
    def seconds(self):
        return self.totalSecond % 60
    
    @property
    def totalMinutes(self):
        return self.t / 60
    
    @property
    def minutes(self):
        return int(self.totalMinutes) % 60
    
    @property
    def totalHours(self):
        return self.t / (60 * 60)
        
    @property
    def hours(self):
        return int(self.totalHours) % 24
    
    @property
    def totalDays(self):
        return self.t / (60 * 60 * 24)


    @property
    def dayPart(self):
        return DayTime(hours=self.hours, minutes=self.minutes, seconds = self.seconds)
        
    @property
    def days(self):
        return int(self.totalDays)
        
    def __str__(self):
        daypart = ""
        if self.totalDays >= 1:
            daypart = "{0}d".format(self.days)
        return daypart + "{0.hours:02d}:{0.minutes:02d}:{0.seconds:06.3f}".format(self)       
        
    def __float__(self):
        return float(self.t)
    
    def __int__(self):
        return int(self.t)
    
    def __eq__(self, other):
        return self.t == other.t
    
    def __lt__(self, other):
        return self.t < other.t
    

