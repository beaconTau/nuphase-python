#!/usr/bin/python
import nuphase
import time
import numpy

NUM_TRIES = 10
NUM_CHANNELS = 8
verbose=True
align_status_file = '/home/nuphase/nuphase_python/output/align_status'
check_align_file  = '/home/nuphase/nuphase_python/output/align_check'

def init(verbose=verbose, reset_shift_bytes=True):
    sys = nuphase.Nuphase()
    sys.boardInit(verbose=verbose)
    current_atten_values = sys.getCurrentAttenValues(verbose=True)
    sys.setAttenValues(numpy.zeros(NUM_CHANNELS, dtype=int), readback=verbose)
    sys.calPulser(True, readback=verbose) #turn on cal pulse feature

    SHIFT_BYTES = numpy.zeros(NUM_CHANNELS, dtype=int)
    if reset_shift_bytes:
        #set to 0 and read in current values for delay:
        ##master board
        for i in range(4):
            sys.write(sys.BUS_MASTER, [56+i,0,0,0])
            readback = sys.readRegister(sys.BUS_MASTER, 56+i)
            SHIFT_BYTES[2*i] = readback[3]
            SHIFT_BYTES[2*i+1] = readback[2]
    
    return sys, SHIFT_BYTES, current_atten_values

def getPeaks(data, mode=1, channels=[0,7]):
    location_of_peaks=[]

    #SHOULD MAKE THIS MORE CONFIGURABLE:
    pulse_threshold_master = 75
    ###########################################
    pulse_thresholds = [pulse_threshold_master] * 8
 
    for chan in range(len(data)):
        if chan < channels[0] or chan > channels[1]:
            continue
        ##mode = 0, simply use numpy.argmax
        if mode == 0:
            location_of_peaks.append(numpy.argmax(data[chan]))
            
        ##mode = 1, a bit more complicated and board-specific
        elif mode == 1:
            location_of_peaks_temp = numpy.where(numpy.transpose(data[chan]) > pulse_thresholds[chan])[0]
            if len(location_of_peaks_temp) < 1:
                location_of_peaks.append(-1)
            else:
                location_of_peaks.append(location_of_peaks_temp[0])

    return location_of_peaks

def alignInit(sys):
    sys.boardInit()
    print 'checking ADC data good flags..'
    while (sys.getDataValid() != 1):
        time.sleep(1)
    print '...good\n'
    sys.boardInit()
    sys.softwareTrigger()
    sys.readSysEvent(save=False)
    sys.boardInit()
            
def align(NUM_TRIES=10):
    sys, SHIFT_BYTES, current_atten_values = init()
    
    alignInit(sys)
    
    for i in range(NUM_TRIES):
        sys.boardInit()  #only deal with buffer 0
        sys.calPulser(True)
        sys.softwareTrigger()
        time.sleep(0.001)
        data = sys.readSysEvent(save=False)


        location_of_peaks = getPeaks(data, channels=[0,7])

        earliest_peak = min(location_of_peaks)
        earliest_peak_ch = numpy.argmin(location_of_peaks)
        latest_peak = max(location_of_peaks)
        latest_peak_ch = numpy.argmax(location_of_peaks)

        #condition if peaks caught from multiple pulses
        if (latest_peak - earliest_peak) > 300:
            if verbose:
                print i, location_of_peaks, "skipping, trying again..."
            continue

        #condition if not within 16 samples, try a dclk reset
        elif (latest_peak - earliest_peak) > 32:
            sys.dclkReset()
            if verbose:
                print 'sending dclk reset to boards..'
            time.sleep(2)
            if verbose:
                print sys.readRegister(1,8), sys.readRegister(0,8)
                print i, location_of_peaks, 'sample diff', latest_peak-earliest_peak
            time.sleep(1)
            sys.boardInit()
            sys.softwareTrigger()
            #dump event
            dat=sys.readSysEvent(save=False)
            continue

    
        check_peak_location=True
        sum_of_peak_location = 0
        for i in range(2,len(location_of_peaks),2):
            sum_of_peak_location = sum_of_peak_location + location_of_peaks[i-2]
            if location_of_peaks[i] != location_of_peaks[i-2]:
                check_peak_location=False
                break

        #if 'sum of peak location' is 0, found peaks in all channels at index=0, which might happen on startup (for some reason?)
        if sum_of_peak_location == 0:
            print 'found all zeros for peak index, trying again'
            time.sleep(1)
            continue
        elif sum_of_peak_location < 0:
            print 'issue found, no peaks, trying reset'
            print location_of_peaks
            print 'sending reset...'
            sys.reset()
            time.sleep(30)
            alignInit(sys)
            continue
            
        #otherwise, try to align
        #if location_of_peaks[0] == location_of_peaks[2] == location_of_peaks[4] ==\
        #   location_of_peaks[6] == location_of_peaks[8] == location_of_peaks[10]:
        if check_peak_location:
            if verbose:
                print 'alignment successful: ', location_of_peaks
                print 'SHIFT BYTES:', SHIFT_BYTES
            sys.readSysEvent(save=True, filename='output/test_alignment.dat') #save pulse event for verification
            close(sys, current_atten_values, verbose=verbose)
            return 1

        if verbose:
            print location_of_peaks, 'sample diff', latest_peak-earliest_peak
        #system has 12 channels = 6 ADC shift values
        for j in range(4):
            shift_value = latest_peak - location_of_peaks[2*j]+1
            if shift_value != 0:
                #should be identical for both channels within an ADC
                SHIFT_BYTES[2*j] = 0x00  | True << 4 | (shift_value & 0xF)
                SHIFT_BYTES[2*j+1] = 0x00 | True << 4 | (shift_value & 0xF)
                sys.write(sys.BUS_MASTER, [56+j,0,SHIFT_BYTES[2*j+1], SHIFT_BYTES[2*j]])

    
    close(sys, current_atten_values, verbose=verbose)
    return 0

def close(sys, atten_values, verbose):
    sys.boardInit(verbose=verbose)
    sys.calPulser(False, readback=verbose)
    sys.setAttenValues(atten_values, readback=verbose)


def checkAlignment(channels=[0,7], NUM_TRIES=50, verbose=False):
    num_tests=0
    num_success=0
    num_almost_success=0

    sys, _, current_atten_values = init(reset_shift_bytes=False)

    for i in range(NUM_TRIES):
        sys.boardInit()  #only deal with buffer 0
        sys.calPulser(True)
        sys.softwareTrigger()
        time.sleep(0.001)
        data = sys.readSysEvent(save=False)
        if verbose:
            print sys.getMetaData()
        location_of_peaks = getPeaks(data, channels=channels)
        earliest_peak = min(location_of_peaks)
        latest_peak = max(location_of_peaks)

        #condition if peaks caught from multiple pulses
        if (latest_peak - earliest_peak) > 300:
            if verbose:
                print i, location_of_peaks, "skipping, trying again..."
            continue

        num_tests=num_tests+1

        check_peak_location=True
        for i in range(2,len(location_of_peaks),2):
            if location_of_peaks[i] != location_of_peaks[i-2]:
                check_peak_location=False
                break
                                                  
        #otherwise, try to align
        #if location_of_peaks[0] == location_of_peaks[2] == location_of_peaks[4] ==\
        #   location_of_peaks[6] == location_of_peaks[8] == location_of_peaks[10]:
        if check_peak_location:
            if verbose:
                print 'alignment successful: ', location_of_peaks
            #sys.readSysEvent(save=True, filename='test_alignment.dat') #save pulse event for verification
            num_success=num_success+1
        else:
            if verbose:
                print i, 'DATA ARE NOT ALIGNED..', location_of_peaks, earliest_peak, latest_peak
            if abs(latest_peak - earliest_peak) == 1:
                num_almost_success = num_almost_success + 1
                
    sys.boardInit()
    sys.calPulser(False, readback=True)
    print '-------------------------'
    print 'RESULTS:', num_success, 'pure successes out of', num_tests, 'tries'
    print 'RESULTS:', num_success+num_almost_success, '>= almost successes (+/-1) out of', num_tests, 'tries'

    return num_success, num_tests

##--------------------
##run >>python align_adcs.py            to align board timestreams
##run >>python align_adcs.py -c         to verify alignment
if __name__=="__main__":
    import sys
    from optparse import OptionParser

    parser = OptionParser()
    usage = "usage: %prog [options]"
    parser.add_option("-c", "--check", action="store_const", dest="check", const=True)
    #parser.add_option("-m", "--master-only", action="store_const", dest="master", const=True)
    (options, args) = parser.parse_args()


    if options.check:
        num_tries = 50
        #if len(sys.argv) == 3:
        #    num_tries = int(sys.argv[2])
        #if options.master:
        #    success, tests = checkAlignment(NUM_TRIES=num_tries, channels=[0,7])
        #else:
        success, tests = checkAlignment(NUM_TRIES=num_tries)
        file = open(check_align_file, 'w')
        file.write(str(success)+'\n'+str(tests))
        file.close()
            
    else:
        file = open(align_status_file, 'w')
        file.write("0")
        file.close()
        #if options.master:
        #    retval=align(only_master_board=True)
        #else:
        retval=align()
        if retval==0:
            print 'problem here'
        else:
            file = open(align_status_file, 'w')
            file.write("1")
            file.close()
        sys.exit(retval)
 
                                    
        
