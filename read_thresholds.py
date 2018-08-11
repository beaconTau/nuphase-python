import nuphase
import time
import json



d=nuphase.Nuphase()
print d.readAllThresholds()
for beam in range(24):
    d.setBeamThresholds(52000, beam, readback=True)
print d.readAllThresholds()



#current_scalers = d.readScalers()
#print 'current scaler values:', current_scalers



    


