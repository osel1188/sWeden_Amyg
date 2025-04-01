import pyvisa as visa
import time
# start of untitled

SOURce_num_=1
offset=1
UNIT = 'VPP'
SOURce_num_2=2
OUTPut_num_=1
state=True
OUTPut_num_2=2



def DevSet(O_device):
    #Parameters
    function='SIN'
    ohms='INFinity'
    num_cycles = 'INFinity'
    # setting output load to InF
    for i in [1,2]:
        O_device.write(':OUTPut%d:LOAD %s' % (i, ohms))
        
        O_device.write(':SOURce%d:FUNCtion %s' % (i, function))
        
        O_device.write(':SOURce%d:BURSt:NCYCles %s' % (i, num_cycles))
        
        O_device.write(':SOURce%d:BURSt:STATe %d' % (i, True)) 
              # Enable burst mode
        O_device.write(f':SOURce{i}:BURSt:MODE TRIGgered')        # Triggered burst mode
        
        O_device.write(':SOURce%d:BURSt:PHASe %G' % (i, 0))
     
        
        # Make sure outputs are initially off
        O_device.write(f':OUTPut{i}:STATe OFF')
        #O_device.write(':SOURce%d:VOLTage:COUPle:STATe %d' % (i, 1))

rm = visa.ResourceManager()
EDU_Master = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050101::0::INSTR')


EDU_Master.write('*WAI')


EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 11000, 0))
EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 11130, 0))


DevSet(EDU_Master)