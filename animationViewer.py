#!/usr/bin/env python3

import matplotlib.pyplot as plt
import numpy as np
import scipy as sc
from scipy.interpolate import  griddata
import sys
import time

fig, axes = plt.subplots(nrows=2)
fig.show()
cb = [None, None]

while True:
	for dcol in range(2,4):
		d=np.loadtxt(sys.argv[1])

		points=d[:,0:2]
		values=d[:,dcol]

		minx=min(d[:,0])
		maxx=max(d[:,0])

		miny=min(d[:,1])
		maxy=max(d[:,1])


		grid_x, grid_y=np.mgrid[minx:maxx:50j, miny:maxy:50j]


		grid=griddata(points,values,(grid_x,grid_y),method='linear')

		plt.hot()
		i = dcol - 2
		#axes[dcol-2].clear()
		plt.xlabel("number of charging stations (sockets)")
		plt.ylabel("probability of shopping")
		lines=axes[i].contourf(grid_x,grid_y,grid)
		if cb[i] is None:		
			cb[i] = fig.colorbar(lines,ax=axes[dcol-2])
		else:
			cb[i].update_bruteforce(lines)		
		fig.canvas.draw()
	time.sleep(20)
