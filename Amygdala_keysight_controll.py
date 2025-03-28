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
    # setting output load to InF
    for i in [1,2]:
        O_device.write(':OUTPut%d:LOAD %s' % (i, ohms))
        O_device.write(':SOURce%d:FUNCtion %s' % (i, function))
        #O_device.write(':SOURce%d:VOLTage:COUPle:STATe %d' % (i, 1))


Cond = input("put SHAM or STIM::\n ->")
print(print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m"))
Ach1 = input("\033[38;5;27mCHANNEL 1: \n     ->       \033[0m")
Ach2 = input("\033[38;5;27mCHANNEL 2: \n     ->       \033[0m")
Ach3 = input("\033[38;5;27mCHANNEL 3: \n     ->       \033[0m")
Ach4 = input("\033[38;5;27mCHANNEL 4: \n     ->       \033[0m")


    

rm = visa.ResourceManager()
EDUA = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050190::0::INSTR')
EDUB = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050101::0::INSTR')
print("KeySights_Connectee")

EDUA.write('*RST')
EDUB.write('*RST')
DevSet(EDUA)
DevSet(EDUB)

# Settings

EDUA.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0.5))
EDUA.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9130, 0.5))

EDUB.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0.5))
EDUB.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7130, 0.5))


#### START - 0.00000001 s #####
EDUA.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDUA.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDUB.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDUB.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

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
time.sleep(10)
### END of stim 
state =False
EDUA.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDUA.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

EDUB.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))
EDUB.write(':OUTPut%d:STATe %d' % (OUTPut_num_2, state))

#shotScreen(EDU33212A)


##


EDUA.close()
EDUB.close()
rm.close()

# end of untitled
