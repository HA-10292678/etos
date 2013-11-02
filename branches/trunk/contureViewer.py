#!/usr/bin/env python3

import matplotlib.pyplot as plt
import numpy as np
import scipy as sc
from scipy.interpolate import  griddata
import sys

d=np.loadtxt(sys.argv[1])
dcol = int(sys.argv[2])

points=d[:,0:2]
values=d[:,dcol]

minx=min(d[:,0])
maxx=max(d[:,0])

miny=min(d[:,1])
maxy=max(d[:,1])


grid_x, grid_y=np.mgrid[minx:maxx:50j, miny:maxy:50j]


grid=griddata(points,values,(grid_x,grid_y),method='linear')

#plt.contourf(grid_x,grid_y,grid)
plt.hot()
plt.xlabel("number of charging stations (sockets)")
plt.ylabel("probability of shopping")
lines=plt.contourf(grid_x,grid_y,grid)
#plt.clabel(lines, inline=1, fontsize=10, fmt='%.3f')
plt.colorbar()
plt.show()
