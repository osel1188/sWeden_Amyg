
import pyvisa as visa
import numpy as np
import time
import keyboard
import threading
import os
import sys


SOURce_num_=1
SOURce_num_2=2
OUTPut_num_=1
state=True
OUTPut_num_2=2
CURRENTVOLTAGE = [0,0,0,0]



def listen_keys():

    while True:
        

        if keyboard.is_pressed('u'):
            print("\033[33m[U] Quit!\033[0m")

            print("\033[1;31mURGENT_EMERGENCY_STOP_TRIGGERED\033[0m")
            print("\033[1;31mExiting....\033[0m")
            EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, False))
            EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, False))

            EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, False))
            EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, False))

            time.sleep(0.5)
            EDU_Master.clear()

            EDU_Master.close()
            EDU_Slave_1.close()
            os._exit(0)
            break
        time.sleep(0.1)  # nemazat

# Start keyboard listener in a separate thread
listener = threading.Thread(target=listen_keys, daemon=True)
listener.start()


def ramp(Devs,endAmplitude,duration):
    
    step = [0,0,0,0] 
    spinner = ['◜', '◝', '◞', '◟']

    numberOf100msTimeSteps = duration * 10


    for i in range(0,len(step)):
   
        step[i] = (endAmplitude[i]-CURRENTVOLTAGE[i])/numberOf100msTimeSteps
    
    start=time.time()
    for i in range(0,numberOf100msTimeSteps):
        
        sys.stdout.flush()
        sys.stdout.write(f'\r Ramping .....   {spinner[i%4]}')
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
           
      
        time.sleep(0.1)

    stop = time.time()

    print("\n")
    print(f"ToR__{stop-start}")
   

def send_command(input, which_one):
    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')

    if which_one == 'slave':
        EDU_Slave_1.write(input)
    elif which_one == 'master':
        EDU_Master.write(input)
    


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
 

Cond = str(input("put SHAM or STIM::\n ->")).upper().strip()
rm = visa.ResourceManager()

EDU_Master = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050087::0::INSTR')
EDU_Slave_1 = rm.open_resource('USB0::0x2A8D::0x8D01::CN62490141::0::INSTR')



EDU_Master.clear()
EDU_Slave_1.clear()

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')

time.sleep(1)


print("KeySights Connected")

if Cond == 'STIM':
    print(f"Condition {Cond} Selected")
    print("==========================")

    send_command(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0), 'master')
    send_command(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9130, 0), 'master')

    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0))
    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7130, 0))
elif Cond == "SHAM":
    print(f"Condition {Cond} Selected")
    print("==========================")
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0))
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9000, 0))

    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')

    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0))
    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7000, 0))
else:
    print("\033[1;31mWRONG CONDITION\033[0m")
    print("Exiting....")
    EDU_Master.close()
    EDU_Slave_1.close()
    os._exit(0)

print(print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m"))
Ach1 = np.abs(float(input("\033[38;5;27mCHANNEL 1: \n     ->       \033[0m")))
Ach2 = np.abs(float(input("\033[38;5;27mCHANNEL 2: \n     ->       \033[0m")))
Ach3 = np.abs(float(input("\033[38;5;27mCHANNEL 3: \n     ->       \033[0m")))
Ach4 = np.abs(float(input("\033[38;5;27mCHANNEL 4: \n     ->       \033[0m")))

if any(x > 8 for x in [Ach1, Ach2, Ach3, Ach4]):
    print("\033[1;31mSafety____protocol__TRIGGER\033[0m")
    print("\033[1;31mAmplitude reference Exceed safety limit\033[0m")
    print("Exiting....")
    os._exit(0)

for O_device in [EDU_Master,EDU_Slave_1]:
    for i in [1,2]:
        O_device.write(f':OUTPut{i}:STATe OFF')


DevSet(EDU_Master)
DevSet(EDU_Slave_1)


EDU_Master.write(f':TRIGger{1}:SOURce BUS') 
EDU_Master.write(f':TRIGger{2}:SOURce BUS')
#ime.sleep(1)
EDU_Master.write(':OUTPut%d:TRIGger:STATe %d' % (1, True))
time.sleep(1)   # NEMAZAT 
EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
 

state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))
time.sleep(1)

print("\033[95m🔬 Amplitude vectors aligned. Stimulation system standing by.\033[0m")

while state != 'f':
    state = input("[Press [s] to start stimulation, [e] to end stimulation, [b] to beep, [q] to (quit)]   [s/e/b/q][start/end/beep/quit]:: ")
    if state == "s":
        current_values = [float(EDU_Master.query('SOUR1:VOLT?')),float(EDU_Master.query('SOUR2:VOLT?')),float(EDU_Slave_1.query('SOUR1:VOLT?')),float(EDU_Slave_1.query('SOUR2:VOLT?'))]
        if any(x >= 0.1 for x in current_values):
            print("Cant ramp up from non zero amplitude as starting point!")
            for val in current_values:
                print(f"Value:: {val}")
            continue
        print("Ramping up start")
        state = True

        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))


        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        
        time.sleep(0.5)

        EDU_Master.write(f':TRIGger{1}:SOURce BUS') 
        EDU_Master.write(f':TRIGger{2}:SOURce BUS')
        time.sleep(1)
        EDU_Master.write(':OUTPut%d:TRIGger:STATe %d' % (1, True))
        time.sleep(1)   # NEMAZAT 
        EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
        time.sleep(1)  # NEMAZAT 

        EDU_Master.write('*TRG')
        ramp([EDU_Master,EDU_Slave_1],[Ach1,Ach2,Ach3,Ach4],60)
        print("\033[33mRamping up finished\033[0m")
        
    elif state == "e":
        print("Ramping down start")

        
        ramp([EDU_Master,EDU_Slave_1],[0,0,0,0],60)

        time.sleep(1)
        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        
        time.sleep(1)
        EDU_Master.write(f':ABORt')
        EDU_Slave_1.write(f':ABORt')
        
        EDU_Master.clear()
        time.sleep(0.1)
        state = False

        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
        EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

        print("\033[33mRamping down finished\033[0m")

    elif state == "b":
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        
        time.sleep(0.15)
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
        
    elif state == "q":
        EDU_Master.clear()
        EDU_Slave_1.clear()
        print("Exiting")
        break
    else:
        print("\033[1;31mWrong Input\033[0m")


EDU_Master.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')

time.sleep(0.15)
EDU_Master.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')


state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

time.sleep(1)
EDU_Master.close()
EDU_Slave_1.close()

rm.close()



