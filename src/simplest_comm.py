
import pyvisa as visa
import numpy as np
import time
import keyboard
import threading
import os
import sys


if __name__ == "__main__":
    rm = visa.ResourceManager()

    EDU_Master = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050087::0::INSTR')
    EDU_Slave_1 = rm.open_resource('USB0::0x2A8D::0x8D01::CN62490141::0::INSTR')

    EDU_Master.clear()
    EDU_Slave_1.clear()

    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')

    time.sleep(1)
    print("KeySights Connected")

    EDU_Master.write(':SOURce1:APPLy:SINusoid 9000,0')
    EDU_Master.write(':SOURce2:APPLy:SINusoid 9130,0')
    EDU_Slave_1.write(':SOURce1:APPLy:SINusoid 7000,0')
    EDU_Slave_1.write(':SOURce2:APPLy:SINusoid 7130,0')

    # ---- MASTER - OUTPUT 1 ----
    EDU_Master.write(':OUTPut1:STATe OFF')
    EDU_Master.write(':OUTPut1:LOAD INFinity')
    # ---- MASTER - SOURCE 1 ----
    EDU_Master.write(':SOURce1:FUNCtion SIN')
    EDU_Master.write(':SOURce1:BURSt:NCYCles INFinity')
    EDU_Master.write(':SOURce1:BURSt:STATe 1') 
    EDU_Master.write(':SOURce1:BURSt:MODE TRIGgered')        # enable Triggered burst mode
    EDU_Master.write(':SOURce1:BURSt:PHASe 0')
    # ---- MASTER - OUTPUT 2 ----
    EDU_Master.write(':OUTPut2:STATe OFF')
    EDU_Master.write(':OUTPut2:LOAD INFinity')
    # ---- MASTER - SOURCE 2 ----
    EDU_Master.write(':SOURce2:FUNCtion SIN')
    EDU_Master.write(':SOURce2:BURSt:NCYCles INFinity')
    EDU_Master.write(':SOURce2:BURSt:STATe 1') 
    EDU_Master.write(':SOURce2:BURSt:MODE TRIGgered')        # Triggered burst mode
    EDU_Master.write(':SOURce2:BURSt:PHASe 0')
    
    # ---- SLAVE - OUTPUT 1 ----
    EDU_Slave_1.write(':OUTPut1:STATe OFF')
    EDU_Slave_1.write(':OUTPut1:LOAD INFinity')
    # ---- SLAVE - SOURCE 1 ----
    EDU_Slave_1.write(':SOURce1:FUNCtion SIN')
    EDU_Slave_1.write(':SOURce1:BURSt:NCYCles INFinity')
    EDU_Slave_1.write(':SOURce1:BURSt:STATe 1') 
    EDU_Slave_1.write(':SOURce1:BURSt:MODE TRIGgered')        # enable Triggered burst mode
    EDU_Slave_1.write(':SOURce1:BURSt:PHASe 0')
    # ---- SLAVE - OUTPUT 2 ----
    EDU_Slave_1.write(':OUTPut2:STATe OFF')
    EDU_Slave_1.write(':OUTPut2:LOAD INFinity')
    # ---- SLAVE - SOURCE 2 ----
    EDU_Slave_1.write(':SOURce2:FUNCtion SIN')
    EDU_Slave_1.write(':SOURce2:BURSt:NCYCles INFinity')
    EDU_Slave_1.write(':SOURce2:BURSt:STATe 1') 
    EDU_Slave_1.write(':SOURce2:BURSt:MODE TRIGgered')        # Triggered burst mode
    EDU_Slave_1.write(':SOURce2:BURSt:PHASe 0')

    EDU_Master.write(':TRIGger1:SOURce BUS') 
    EDU_Master.write(':TRIGger1:SOURce BUS')
    EDU_Master.write(':OUTPut1:TRIGger:STATe 1')
    time.sleep(1)   # NEMAZAT 
    EDU_Slave_1.write(':TRIGger1:SOURce EXTernal') 
    EDU_Slave_1.write(':TRIGger2:SOURce EXTernal') 
    
    # Make sure outputs are initially off
    EDU_Master.write(':OUTPut1:STATe OFF')
    EDU_Master.write(':OUTPut2:STATe OFF')
    EDU_Slave_1.write(':OUTPut1:STATe OFF')
    EDU_Slave_1.write(':OUTPut2:STATe OFF')
    time.sleep(1)

    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')
    time.sleep(0.5)

    print("\033[95m🔬 Amplitude vectors aligned. Stimulation system standing by.\033[0m")


    current_values = [float(EDU_Master.query('SOUR1:VOLT?')),
                      float(EDU_Master.query('SOUR2:VOLT?')),
                      float(EDU_Slave_1.query('SOUR1:VOLT?')),
                      float(EDU_Slave_1.query('SOUR2:VOLT?'))]


    EDU_Master.write(':OUTPut1:STATe ON')
    EDU_Master.write(':OUTPut2:STATe ON')
    EDU_Slave_1.write(':OUTPut1:STATe ON')
    EDU_Slave_1.write(':OUTPut2:STATe ON')

    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')
    time.sleep(0.5)


    duration = 10  # seconds
    step = [0,0,0,0] 
    spinner = ['◜', '◝', '◞', '◟']
    numberOf100msTimeSteps = duration * 10
    CURRENTVOLTAGE = [0,0,0,0]
    Devs = [EDU_Master,EDU_Slave_1]
    endAmplitude = [2, 2, 2, 2]

    for i in range(0,len(step)):
        step[i] = (endAmplitude[i]-CURRENTVOLTAGE[i])/numberOf100msTimeSteps
    
    EDU_Master.write('*TRG')
    start=time.time()
    for i in range(0,numberOf100msTimeSteps):
        sys.stdout.flush()
        sys.stdout.write(f'\r Ramping .....   {spinner[i%4]}')
        for j in range(0, len(step)):
            CURRENTVOLTAGE[j] += step[j]
            if CURRENTVOLTAGE[j] <= 0:
                    CURRENTVOLTAGE[j] = 0

            if j == 0 :
                    Devs[0].write(':SOURce1:VOLTage %G' % CURRENTVOLTAGE[j])
            elif j == 1:
                    Devs[0].write(':SOURce2:VOLTage %G' % CURRENTVOLTAGE[j])
            elif j == 2:
                    Devs[1].write(':SOURce1:VOLTage %G' % CURRENTVOLTAGE[j])
            elif j == 3:
                    Devs[1].write(':SOURce2:VOLTage %G' % CURRENTVOLTAGE[j])
        time.sleep(0.1)
    stop = time.time()
    print("\n")
    print(f"ToR__{stop-start}")


    EDU_Master.clear()
    EDU_Slave_1.clear()
    print("Exiting")

    EDU_Master.write('SYSTem:BEEPer:IMMediate')
    EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')

    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')

    time.sleep(0.15)
    EDU_Master.write('SYSTem:BEEPer:IMMediate')
    EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
    EDU_Master.write('*WAI')
    EDU_Slave_1.write('*WAI')

    EDU_Master.write(':OUTPut1:STATe 0')
    EDU_Master.write(':OUTPut2:STATe 0')
    EDU_Slave_1.write(':OUTPut1:STATe 0')
    EDU_Slave_1.write(':OUTPut2:STATe 0')

    time.sleep(1)
    EDU_Master.close()
    EDU_Slave_1.close()