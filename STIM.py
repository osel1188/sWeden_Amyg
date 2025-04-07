# NOTE: the default pyvisa import works well for Python 3.6+
# if you are working with python version lower than 3.6, use 'import visa' instead of import pyvisa as visa

#import pyvisa as visa

#### Tester -Remove before Flight 

# Dummy VISA replacement
class DummyInstrument:
    def __init__(self, name):
        self.name = name

    def write(self, command):
        print(f"[{self.name}] WRITE: {command}")

    def query_binary_values(self, command, datatype, is_big_endian):
        print(f"[{self.name}] QUERY_BINARY_VALUES: {command}")
        return [0x89, 0x50, 0x4E, 0x47]  # Fake PNG header

    def clear(self):
        print(f"[{self.name}] CLEAR")

    def close(self):
        print(f"[{self.name}] CLOSE")

# Simulated ResourceManager
class DummyResourceManager:
    def open_resource(self, address):
        print(f"[RM] Opening resource: {address}")
        return DummyInstrument(address)

    def close(self):
        print("[RM] ResourceManager closed")


##########################################





import time
# start of untitled

SOURce_num_=1
offset=1
UNIT = 'VPP'
SOURce_num_2=2
OUTPut_num_=1
state=True
OUTPut_num_2=2
CURRENTVOLTAGE = [0,0,0,0]

import keyboard
import threading
import os



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

            EDU_Master.close()
            EDU_Slave_1.close()
            os._exit(0)
            break

# Start keyboard listener in a separate thread
listener = threading.Thread(target=listen_keys, daemon=True)
listener.start()


def ramp(Devs,endAmplitude,duration):

    step = [0,0,0,0] 
    

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
 

Cond = str(input("put SHAM or STIM::\n ->"))
print(print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m"))
Ach1 = float(input("\033[38;5;27mCHANNEL 1: \n     ->       \033[0m"))
Ach2 = float(input("\033[38;5;27mCHANNEL 2: \n     ->       \033[0m"))
Ach3 = float(input("\033[38;5;27mCHANNEL 3: \n     ->       \033[0m"))
Ach4 = float(input("\033[38;5;27mCHANNEL 4: \n     ->       \033[0m"))

if any(x > 8 for x in [Ach1, Ach2, Ach3, Ach4]):
    print("\033[1;31mSafety____protocol__TRIGGER\033[0m")
    print("\033[1;31mAmplitude reference Exceed safety limit\033[0m")
    print("Exiting....")
    os._exit(0)


    
# Here also change to visa.ResourceManager before real experiment 
rm = DummyResourceManager()
# rm = visa.ResourceManager()
EDU_Master = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050101::0::INSTR')
EDU_Slave_1 = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050190::0::INSTR')

EDU_Master.clear()
EDU_Slave_1.clear()

print("KeySights Connected")

time.sleep(1)

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')


EDU_Master.write('*RST')
EDU_Slave_1.write('*RST')

time.sleep(1)

for O_device in [EDU_Master,EDU_Slave_1]:
    for i in [1,2]:
        O_device.write(f':OUTPut{i}:STATe OFF')

time.sleep(1)

if Cond == 'STIM':
    print("Condition {Cond} Selected")
    print("==========================")
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0))
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9130, 0))

    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0))
    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7130, 0))
elif Cond == "SHAM":
    print("Condition {Cond} Selected")
    print("==========================")
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0))
    EDU_Master.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9000, 0))

    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0))
    EDU_Slave_1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7000, 0))
else:
    print("\033[1;31mWRONG CONDITION\033[0m")
    print("Exiting....")
    EDU_Master.close()
    EDU_Slave_1.close()
    os._exit(0)



DevSet(EDU_Master)
DevSet(EDU_Slave_1)


EDU_Master.write(f':TRIGger{1}:SOURce BUS') 
EDU_Master.write(f':TRIGger{2}:SOURce BUS')
time.sleep(1)
EDU_Master.write(':OUTPut%d:TRIGger:STATe %d' % (1, True))
time.sleep(1)   # NEMAZAT KURVA JE TO DULEZITE
EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
 

state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))





 
# Settings
#### START - 0.00000001 s #####
time.sleep(1)
# Enable trigger

print("\033[95m🔬 Amplitude vectors aligned. Stimulation system standing by.\033[0m")


while state != 'f':
    state = input("[Press [s] to start stimulation, [e] to end stimulation, [b] to beep, [q] to (quit)]   [s/e/b/q][start/end/beep/quit]:: ")
    if state == "s":
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
        time.sleep(1)   # NEMAZAT KURVA JE TO DULEZITE
        EDU_Slave_1.write(f':TRIGger{1}:SOURce EXTernal') 
        EDU_Slave_1.write(f':TRIGger{2}:SOURce EXTernal') 
        

        EDU_Master.write('*TRG')
        ramp([EDU_Master,EDU_Slave_1],[Ach1,Ach2,Ach3,Ach4],5)
        print("Ramping up finished")
    elif state == "e":
        print("Ramping down start")
        ramp([EDU_Master,EDU_Slave_1],[0,0,0,0],5)

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

        print("Ramping down finished")

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

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')

time.sleep(0.15)
EDU_Master.write('SYSTem:BEEPer:IMMediate')
EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')

#time.sleep(10)
### END of stim 

EDU_Master.write('*WAI')
EDU_Slave_1.write('*WAI')


state = False

EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Master.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDU_Slave_1.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

time.sleep(1)
#shotScreen(EDU33212A)


##

EDU_Master.close()
EDU_Slave_1.close()

rm.close()

# end of untitled
