#!/usr/bin/env python3
import matplotlib.pyplot as plt
import math

def charging2(voltage, current,cellVoltage, energy, capacity, duration):
    capacity=(capacity*1000)/cellVoltage
    energy=(energy*1000)/cellVoltage
    time=((capacity/current)*14)/10 
    timeTo80=(capacity*80/100)/current  
    asp=100*energy/capacity #actual state in percent
    timeToActual=(capacity*asp/100)/current
    breakpoint=80*capacity/100
    
    if duration>=time:#-timeToActual:
        return capacity
    
    
    if(duration<timeTo80 or energy+current*duration<breakpoint):
       energy=current*duration
    else:
        k=duration*current*10/capacity
        print('k=',k)
        if k<10:
            k=10.6
        if k>10.1 and k<=11.5:
            k+=0.5
        if k>11.3 and k<=12:
            k+=0.4
        
        if k>12 and k<=12.5:
            k+=0.35
        if k>12.5 and k<=12.8:
            k+=0.25
        if k>12.8 and k<=13:
            k+=0.2
        if k>13 and k<=13.2:
            k+=0.1
        energy=duration*current*10/k
                    
    print(energy)         
    return energy

pole=[]
pole2=[]
for i in range(15):
    pole.append(i)
    pole2.append(charging2(230,8,324,0,26,i))
plt.plot(pole,pole2)
plt.grid()
plt.show()
