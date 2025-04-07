import time

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

# Dummy ramping setup
SOURce_num_ = 1
offset = 1
UNIT = 'VPP'
SOURce_num_2 = 2
OUTPut_num_ = 1
state = True
OUTPut_num_2 = 2
CURRENTVOLTAGE = [0, 0, 0, 0]




import keyboard
import threading

def listen_keys():
    while True:
        if keyboard.is_pressed('u'):
            print("\033[33m[U] Quit!\033[0m")
            break

# Start keyboard listener in a separate thread
listener = threading.Thread(target=listen_keys, daemon=True)
listener.start()



def ramp(Devs, endAmplitude, duration):
    step = [0, 0, 0, 0]
    numberOf100msTimeSteps = duration * 10

    for i in range(0, len(step)):
        step[i] = (endAmplitude[i] - CURRENTVOLTAGE[i]) / numberOf100msTimeSteps

    for i in range(numberOf100msTimeSteps):
        for j in range(0, len(step)):
            CURRENTVOLTAGE[j] += step[j]
            if CURRENTVOLTAGE[j] <= 0:
                CURRENTVOLTAGE[j] = 0

            if j == 0:
                Devs[0].write(f':SOURce1:VOLTage {CURRENTVOLTAGE[j]}')
            elif j == 1:
                Devs[0].write(f':SOURce2:VOLTage {CURRENTVOLTAGE[j]}')
            elif j == 2:
                Devs[1].write(f':SOURce1:VOLTage {CURRENTVOLTAGE[j]}')
            elif j == 3:
                Devs[1].write(f':SOURce2:VOLTage {CURRENTVOLTAGE[j]}')

        time.sleep(0.1)

def shotScreen(O_device):
    temp_values = O_device.query_binary_values(':HCOPy:SDUMp:DATA?', 's', False)
    with open('screenshot.png', 'wb') as file:
        file.write(bytearray(temp_values))
    print("Screenshot saved as 'screenshot.png'")

def DevSet(O_device):
    function = 'SIN'
    ohms = 'INFinity'
    num_cycles = 'INFinity'

    for i in [1, 2]:
        O_device.write(f':OUTPut{i}:LOAD {ohms}')
        O_device.write(f':SOURce{i}:FUNCtion {function}')
        O_device.write(f':SOURce{i}:BURSt:NCYCles {num_cycles}')
        O_device.write(f':SOURce{i}:BURSt:STATe 1')
        O_device.write(f':SOURce{i}:BURSt:MODE TRIGgered')
        O_device.write(f':SOURce{i}:BURSt:PHASe 0')
        O_device.write(f':OUTPut{i}:STATe OFF')

# --- Simulated script logic ---

Cond = input("put SHAM or STIM::\n ->")
print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m")
Ach1 = float(input("\033[38;5;27mCHANNEL 1: \n     ->       \033[0m"))
Ach2 = float(input("\033[38;5;27mCHANNEL 2: \n     ->       \033[0m"))
Ach3 = float(input("\033[38;5;27mCHANNEL 3: \n     ->       \033[0m"))
Ach4 = float(input("\033[38;5;27mCHANNEL 4: \n     ->       \033[0m"))

rm = DummyResourceManager()
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

for O_device in [EDU_Master, EDU_Slave_1]:
    for i in [1, 2]:
        O_device.write(f':OUTPut{i}:STATe OFF')

time.sleep(1)

EDU_Master.write(':SOURce1:APPLy:SINusoid 11000,0')
EDU_Master.write(':SOURce2:APPLy:SINusoid 11130,0')
EDU_Slave_1.write(':SOURce1:APPLy:SINusoid 9000,0')
EDU_Slave_1.write(':SOURce2:APPLy:SINusoid 9130,0')

DevSet(EDU_Master)
DevSet(EDU_Slave_1)

EDU_Master.write(':TRIGger1:SOURce BUS')
EDU_Master.write(':TRIGger2:SOURce BUS')
time.sleep(1)
EDU_Master.write(':OUTPut1:TRIGger:STATe 1')
time.sleep(1)
EDU_Slave_1.write(':TRIGger1:SOURce EXTernal')
EDU_Slave_1.write(':TRIGger2:SOURce EXTernal')

state = False

EDU_Master.write(':OUTPut1:STATe 0')
EDU_Master.write(':OUTPut2:STATe 0')
EDU_Slave_1.write(':OUTPut1:STATe 0')
EDU_Slave_1.write(':OUTPut2:STATe 0')

print("I AM READYY FUCKER")
while state != 'f':
    state = input("[Press s to start stimulation, e to end stimulation, b to beep, g to be gay (quit)]:: ")
    if state == "s":
        print("Ramping up start")
        state = True
        for d in [EDU_Master, EDU_Slave_1]:
            d.write(':OUTPut1:STATe 1')
            d.write(':OUTPut2:STATe 1')

        time.sleep(0.5)

        EDU_Master.write(':TRIGger1:SOURce BUS')
        EDU_Master.write(':TRIGger2:SOURce BUS')
        time.sleep(1)
        EDU_Master.write(':OUTPut1:TRIGger:STATe 1')
        time.sleep(1)
        EDU_Slave_1.write(':TRIGger1:SOURce EXTernal')
        EDU_Slave_1.write(':TRIGger2:SOURce EXTernal')

        EDU_Master.write('*TRG')
        ramp([EDU_Master, EDU_Slave_1], [Ach1, Ach2, Ach3, Ach4], 5)
        print("Ramping up finished")

    elif state == "e":
        print("Ramping down start")
        ramp([EDU_Master, EDU_Slave_1], [0, 0, 0, 0], 5)
        time.sleep(1)

        EDU_Master.write('*WAI')
        EDU_Slave_1.write('*WAI')
        time.sleep(1)
        EDU_Master.write(':ABORt')
        EDU_Slave_1.write(':ABORt')
        EDU_Master.clear()

        for d in [EDU_Master, EDU_Slave_1]:
            d.write(':OUTPut1:STATe 0')
            d.write(':OUTPut2:STATe 0')

        print("Ramping down finished")

    elif state == "b":
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')
        time.sleep(0.15)
        EDU_Master.write('SYSTem:BEEPer:IMMediate')
        EDU_Slave_1.write('SYSTem:BEEPer:IMMediate')

    elif state == "g":
        EDU_Master.clear()
        EDU_Slave_1.clear()
        print("Exiting")
        break
    else:
        print("\033[1;31mWrong Input\033[0m")


# Cleanup
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
rm.close()
