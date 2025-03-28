# NOTE: the default pyvisa import works well for Python 3.6+
# if you are working with python version lower than 3.6, use 'import visa' instead of import pyvisa as visa

import pyvisa as visa
import time
# start of untitled

SOURce_num_=1
offset=1
UNIT = 'VPP'
SOURce_num_2=1
OUTPut_num_=1
state=True
OUTPut_num_=1


def shotScreen(O_device):
        # Set screenshot format (BMP, PNG, or JPG)
    temp_values = EDU33212A.query_binary_values(':HCOPy:SDUMp:DATA?','s',False)
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
        EDU33212A.write(':SOURce%d:VOLTage:COUPle:STATe %d' % (i, 1))


Cond = input("put SHAM or STIM::\n ->")
print(print("\033[38;5;220;48;5;18m Please insert measured reference voltage for each Channel for +- 2mA \033[0m"))
Ach1 = input("\033[38;5;27mCHANNEL 1: \n     ->       (27)\033[0m")
Ach2 = input("\033[38;5;27mCHANNEL 1: \n     ->       (27)\033[0m")
Ach3 = input("\033[38;5;27mCHANNEL 1: \n     ->       (27)\033[0m")
Ach4 = input("\033[38;5;27mCHANNEL 1: \n     ->       (27)\033[0m")


    

rm = visa.ResourceManager()
EDU33212A = rm.open_resource('USB0::0x2A8D::0x8D01::CN64050190::0::INSTR')



EDU33212A.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))

EDU33212A.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 5000, 1))

EDU33212A.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 2
EDU33212A.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 1.5
EDU33212A.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 5
EDU33212A.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))
time.sleep(1)
offset = 1

EDU33212A.write(':SOURce%d:VOLTage %s' % (SOURce_num_2, offset))

state =False

# Fn calling
DevSet(EDU33212A)
shotScreen(EDU33212A)


##
EDU33212A.write(':OUTPut%d:STATe %d' % (OUTPut_num_, state))

EDU33212A.close()
EDU33212A.close()
rm.close()

# end of untitled
