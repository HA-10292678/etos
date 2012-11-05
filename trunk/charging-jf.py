def charging(voltage, current, energy, capacity, duration):
	c = capacity * 1000 #to Wh	
	d = duration / 3600.0 #to hour
	ideal_time = c / (voltage * current * 0.8)
	x = d / ideal_time
	renergy = min(energy/capacity + 0.168*x*x*x - 0.78*x*x +1.38*x, 1.0)
	return renergy

for i in range(0, 7200, 900):
	print(i/3600.0, charging(400, 36, 2.4, 24, i))
