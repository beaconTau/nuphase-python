#!/usr/bin/python

#this file can be run as:
# >> ./set_attenuation.py           to set noise level based on hard-coded values
# >> ./set_attenuation.py 4.0  6.0  to set noise level to 4.0 counts on the master board and 6.0 counts on the slave board
# >> ./set_attenuation.py load      to load saved values from atten_file

# reminder that the RMS counts can be higher on the slave board since it is not being used for phasing and can acquire
# with higher vertical resolution
#
# final values saved to file in output/
# file columns are: channel, last written atten value, reversed last written atten value (=number of attenuation ticks),
#                   last std deviation value of noise, target level of noise for channel

import numpy
import nuphase
import time
import sys
import json

DEFINE_NUM_CHAN = 8
TARGET_NOISE_RMS_COUNTS_PHASED_BOARD = 3.9 #3.1 # 4.2
TARGET_NOISE_RMS_COUNTS_RX_BOARD = 7.1
atten_file = '/home/nuphase/nuphase_python/output/atten_values'

def getRMS(data):
    rms = []
    for i in range(len(data)):
        rms.append(round(numpy.std(data[i]),2))

    return rms

def reverseBitsInByte(data):
    reversed_bytes=[]
    for i in range(len(data)):
        reversed_bytes.append(int('{:08b}'.format(data[i])[::-1],2))

    return reversed_bytes

if __name__=='__main__':

    dev=nuphase.Nuphase()
    dev.boardInit()

    #-------------------------------------------
    #don't do scan, load previous values
    if len(sys.argv) > 1:
        if sys.argv[1] == 'load':

            try:
                load_attenuation = numpy.loadtxt(atten_file)
            except IOError:
                print atten_file, 'does not exist, set_attenuation.py needs to be run in non-load mode first'
                sys.exit(1)
        
            load_attenuation_reversed_bits = numpy.array(load_attenuation[:,1], dtype=int)
            dev.setAttenValues(load_attenuation_reversed_bits)

            print 'ATTEN VALUES LOADED. reading back attenuation bytes:', dev.getCurrentAttenValues()
            sys.exit(0)
    #--------------------------------------------

    # otherwise, do scan:
    elif len(sys.argv) == 3:
        TARGET_NOISE_RMS_COUNTS_PHASED_BOARD = float(sys.argv[1])
        TARGET_NOISE_RMS_COUNTS_RX_BOARD = float(sys.argv[2])

        
    TARGET_NOISE_RMS_COUNTS = [TARGET_NOISE_RMS_COUNTS_PHASED_BOARD] * 8
    TARGET_NOISE_RMS_COUNTS.extend([TARGET_NOISE_RMS_COUNTS_RX_BOARD]*4)
    
    dev=nuphase.Nuphase()
    dev.boardInit()
    set_atten_values = numpy.zeros(DEFINE_NUM_CHAN, dtype=int) 
    set_atten_values = reverseBitsInByte(set_atten_values)
    dev.setAttenValues(set_atten_values)

    done=False
    rms_scan_dict = {}
    iter_step = 0
    while(done==False):
        dev.boardInit()
        dev.softwareTrigger()
        data=dev.readSysEvent()
        current_atten_values = dev.getCurrentAttenValues()
        reversed_current_atten_values = reverseBitsInByte(current_atten_values)
        
        rms=getRMS(data)
        print 'rms:', rms
        rms_scan_dict[iter_step] = (reversed_current_atten_values, rms)

        check_good = 0
        for i in range(DEFINE_NUM_CHAN):
            if (rms[i] < TARGET_NOISE_RMS_COUNTS[i]) or (reversed_current_atten_values[i] == 127):
                continue
            else:
                check_good = check_good + 1
                reversed_current_atten_values[i] = reversed_current_atten_values[i] + 1
       
        current_atten_values = reverseBitsInByte(reversed_current_atten_values)
        dev.setAttenValues(current_atten_values, readback=False)

        print 'current atten values:', dev.getCurrentAttenValues()
        print 'reversed bits:', reversed_current_atten_values
        print '------'
        if check_good == 0:
            f = open(atten_file, 'w')
            for j in range(DEFINE_NUM_CHAN):
                f.write(str(j)+'\t'+str(current_atten_values[j])+'\t'+\
                        str(reversed_current_atten_values[j])+'\t'+str(rms[j])+\
                        '\t'+str(TARGET_NOISE_RMS_COUNTS[j])+'\n')
            f.close()
            done = True
        time.sleep(0.1) #a bit of wait time
        iter_step = iter_step + 1

    with open('/home/nuphase/nuphase_python/output/rms_scan.json', 'w') as f:
        json.dump(rms_scan_dict,f)
    print done
    
