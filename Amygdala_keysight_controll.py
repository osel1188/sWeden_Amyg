# NOTE: the default pyvisa import works well for Python 3.6+
# if you are working with python version lower than 3.6, use 'import visa' instead of import pyvisa as visa

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
CURRENTVOLTAGE = [0,0,0,0,0,0,0,0,0,0]

def ramp(Devs,endAmplitude,duration):

    step = [0,0,0,0,0,0,0,0,0,0] 
    

    numberOf100msTimeSteps = duration * 10


    for i in range(0,len(step)):
   
        step[i] = (endAmplitude[i]-CURRENTVOLTAGE[i])/numberOf100msTimeSteps
    

    for i in range(0,numberOf100msTimeSteps):
        for j in range(0,len(step)):
                
            CURRENTVOLTAGE[j] += step[j]
            if CURRENTVOLTAGE[j] <= 0:
                CURRENTVOLTAGE[j] = 0

            if j == 0 :
                Devs[0].write(':SOURce%d:VOLTage %G' % (1, CURRENTVOLTAGE[j]))
            elif j == 1:
                Devs[0].write(':SOURce%d:VOLTage %G' % (2, CURRENTVOLTAGE[j]))
            elif j == 2:
                Devs[1].write(':SOURce%d:VOLTage %G' % (1, CURRENTVOLTAGE[j]))
            elif j == 3:
                Devs[1].write(':SOURce%d:VOLTage %G' % (2, CURRENTVOLTAGE[j]))
            elif j == 4:
                Devs[2].write(':SOURce%d:VOLTage %G' % (1, CURRENTVOLTAGE[j]))
            elif j == 5:
                Devs[2].write(':SOURce%d:VOLTage %G' % (2, CURRENTVOLTAGE[j]))
            elif j == 6:
                Devs[3].write(':SOURce%d:VOLTage %G' % (1, CURRENTVOLTAGE[j]))
            elif j == 7:
                Devs[3].write(':SOURce%d:VOLTage %G' % (2, CURRENTVOLTAGE[j]))
            elif j == 8:
                Devs[4].write(':SOURce%d:VOLTage %G' % (1, CURRENTVOLTAGE[j]))
            elif j == 9:
                Devs[4].write(':SOURce%d:VOLTage %G' % (2, CURRENTVOLTAGE[j]))
      
        time.sleep(0.1)


def shotScreen(O_device):
        # Set screenshot format (BMP, PNG, or JPG)
    temp_values = O_device.query_binary_values(':HCOPy:SDUMp:DATA?','s',False)
    # Save it as a file on the PC

    with open('screenshot.png', 'wb') as file:
        file.write(bytearray(temp_values))

    print("Screenshot saved as 'screenshot.png'")

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
 

Cond = input("put SHAM or STIM::\n ->")
print(print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m"))
Ach1 = float(input("\033[38;5;27mCHANNEL 1: \n     ->       \033[0m"))
Ach2 = float(input("\033[38;5;27mCHANNEL 2: \n     ->       \033[0m"))
Ach3 = float(input("\033[38;5;27mCHANNEL 3: \n     ->       \033[0m"))
Ach4 = float(input("\033[38;5;27mCHANNEL 4: \n     ->       \033[0m"))
Ach5 = float(input("\033[38;5;27mCHANNEL 5: \n     ->       \033[0m"))
Ach6 = float(input("\033[38;5;27mCHANNEL 6: \n     ->       \033[0m"))
Ach7 = float(input("\033[38;5;27mCHANNEL 7: \n     ->       \033[0m"))
Ach8 = float(input("\033[38;5;27mCHANNEL 8: \n     ->       \033[0m"))
Ach9 = float(input("\033[38;5;27mCHANNEL 9: \n     ->       \033[0m"))
Ach10 = float(input("\033[38;5;27mCHANNEL 10: \n     ->       \033[0m"))
    

rm = visa.ResourceManager()
EDU_Master = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050101::0::INSTR')
EDU_Slave_1 = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050190::0::INSTR')
EDU_Slave_2 = rm.open_resource('USB0::0x2A8D::0x8D01::CN61140040::0::INSTR')
EDU_Slave_3 = rm.open_resource('USB0::0x2A8D::0x8D01::CN60450055::0::INSTR')
EDU_Slave_4 = rm.open_resource('USB0::0x2A8D::0x8D01::CN61310039::0::INSTR')
EDU_Master.clear()
EDU_Slave_1.clear()
EDU_Slave_2.clear()
EDU_Slave_3.clear()
EDU_Slave_4.clear()
print("KeySights Connected")

time.sleep(1)

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')
EDU_Slave_2.write('*WAI')
EDU_Slave_3.write('*WAI')
EDU_Slave_4.write('*WAI')

EDU_Master.write('*RST')
EDU_Slave_1.write('*RST')
EDU_Slave_2.write('*RST')
EDU_Slave_3.write('*RST')
EDU_Slave_4.write('*RST')
time.sleep(1)

for O_device in [EDU_Master,EDU_Slave_1,EDU_Slave_2,EDU_Slave_3,EDU_Slave_4]:
    for i in [1,2]:
        O_device.write(f':OUTPut{i}:STATe OFF')

time.sleep(1)


EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 11000, 0))
EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 11130, 0))

EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0))
EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9130, 0))

EDU_Slave_2.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 5000, 0))
EDU_Slave_2.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 5130, 0))

EDU_Slave_3.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 3000, 0))
EDU_Slave_3.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 3130, 0))

EDU_Slave_4.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 1000, 0))
EDU_Slave_4.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 1130, 0))

DevSet(EDU_Master)
DevSet(EDU_Slave_1)
DevSet(EDU_Slave_2)
DevSet(EDU_Slave_3)
DevSet(EDU_Slave_4)

EDU_Master.write(f':TRIGger{1}:SOURce BUS') 
EDU_Master.write(f':TRIGger{2}:SOURce BUS')
time.sleep(1)
EDU_Master.write(':OUTPut%d:TRIGger:STATe %d' % (1, True))
time.sleep(1)   # NEMAZAT KURVA JE TO DULEZITE
EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
EDU_Slave_2.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_2.write(f':TRIGger{2}:SOURce EXTernal') 
EDU_Slave_3.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_3.write(f':TRIGger{2}:SOURce EXTernal') 
EDU_Slave_4.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_4.write(f':TRIGger{2}:SOURce EXTernal') 

state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))



 
# Settings
#### START - 0.00000001 s #####
time.sleep(1)
# Enable trigger

print("I AM READYY FUCKER")
while state != 'f':
    state = input("[Press s to start stimulation, e to end stimulation, b to beep, g to be gay (quit)]:: ")
    if state == "s":
        print("Ramping up start")
        state = True

        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        EDU_Slave_2.write('*WAI')
        EDU_Slave_3.write('*WAI')
        EDU_Slave_4.write('*WAI')
        time.sleep(0.5)

        EDU_Master.write(f':TRIGger{1}:SOURce BUS') 
        EDU_Master.write(f':TRIGger{2}:SOURce BUS')
        time.sleep(1)
        EDU_Master.write(':OUTPut%d:TRIGger:STATe %d' % (1, True))
        time.sleep(1)   # NEMAZAT KURVA JE TO DULEZITE
        EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
        EDU_Slave_2.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_2.write(f':TRIGger{2}:SOURce EXTernal') 
        EDU_Slave_3.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_3.write(f':TRIGger{2}:SOURce EXTernal') 
        EDU_Slave_4.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_4.write(f':TRIGger{2}:SOURce EXTernal') 

        EDU_Master.write('*TRG')
        ramp([EDU_Master,EDU_Slave_1,EDU_Slave_2,EDU_Slave_3,EDU_Slave_4],[Ach1,Ach2,Ach3,Ach4,Ach5,Ach6,Ach7,Ach8,Ach9,Ach10],5)
        print("Ramping up finished")
    elif state == "e":
        print("Ramping down start")
        ramp([EDU_Master,EDU_Slave_1,EDU_Slave_2,EDU_Slave_3,EDU_Slave_4],[0,0,0,0,0,0,0,0,0,0],5)

        time.sleep(1)
        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        EDU_Slave_2.write('*WAI')
        EDU_Slave_3.write('*WAI')
        EDU_Slave_4.write('*WAI')
        time.sleep(1)
        EDU_Master.write(f':ABORt')
        EDU_Slave_1.write(f':ABORt')
        EDU_Slave_2.write(f':ABORt')
        EDU_Slave_3.write(f':ABORt')
        EDU_Slave_4.write(f':ABORt')
        EDU_Master.clear()
        time.sleep(0.1)
        state = False

        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))
        print("Ramping down finished")

    elif state == "b":
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_2.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_3.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_4.write('SYSTem:BEEPer:IMMediate')
        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        EDU_Slave_2.write('*WAI')
        EDU_Slave_3.write('*WAI')
        EDU_Slave_4.write('*WAI')
        time.sleep(0.15)
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_2.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_3.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_4.write('SYSTem:BEEPer:IMMediate')
    elif state == "g":
        EDU_Master.clear()
        EDU_Slave_1.clear()
        EDU_Slave_2.clear()
        EDU_Slave_3.clear()
        EDU_Slave_4.clear()
        print("Exiting")
        break


'''
EDUA.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDUA.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 2
EDUA.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 1.5
EDUA.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 5
EDUA.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 1


EDUA.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
'''

EDU_Master.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_2.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_3.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_4.write('SYSTem:BEEPer:IMMediate')
EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')
EDU_Slave_2.write('*WAI')
EDU_Slave_3.write('*WAI')
EDU_Slave_4.write('*WAI')
time.sleep(0.15)
EDU_Master.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_2.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_3.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_4.write('SYSTem:BEEPer:IMMediate')
#time.sleep(10)
### END of stim 

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')
EDU_Slave_2.write('*WAI')
EDU_Slave_3.write('*WAI')
EDU_Slave_4.write('*WAI')

state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_2.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_3.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_4.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))
time.sleep(1)
#shotScreen(EDU33212A)


##

EDU_Master.close()
EDU_Slave_1.close()
EDU_Slave_2.close()
EDU_Slave_3.close()
EDU_Slave_4.close()
rm.close()

# end of untitled
