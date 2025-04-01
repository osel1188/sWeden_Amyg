import pyvisa as visa
import time




def sync_two_devices(device1_address, device2_address):
    """
    Synchronize two separate Keysight function generators to start at exactly the same time.
    
    Args:
        device1_address: VISA address for the first device (master)
        device2_address: VISA address for the second device (slave)
    """

    SOURce_num_=1
    offset=1
    UNIT = 'VPP'
    SOURce_num_2=2
    OUTPut_num_=1
    state=True
    OUTPut_num_2=2
    # Create resource manager
    rm = visa.ResourceManager()
    
    # Open connections to both devices
    device1 = rm.open_resource(device1_address)  # Master
    device2 = rm.open_resource(device2_address)  # Slave
    
    # Reset both devices
    device1.write('*RST')
    device2.write('*RST')
    
    # Basic settings
    function = 'SIN'
    ohms = 'INFinity'
    num_cycles = 'INFinity'
    
    # Configure both devices using your DevSet function
    for device in [device1, device2]:
        for i in [1, 2]:
            device.write(f':OUTPut{i}:LOAD {ohms}')
            device.write(f':SOURce{i}:FUNCtion {function}')
            device.write(f':SOURce{i}:BURSt:NCYCles {num_cycles}')
            device.write(f':OUTPut{i}:STATe OFF')  # Ensure outputs are off initially
            
    device1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 9000, 0.5))
    device1.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 9130, 0.5))

    device2.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_, 7000, 0.5))
    device2.write(':SOURce%d:APPLy:SINusoid %s,%s' % (SOURce_num_2, 7130, 0.5))
    # =========== SYNCHRONIZATION SETUP ===========
    # 1. Configure device1 as master with 10MHz reference out
    device1.write(':OUTPut:SYNC:SOURce CH1')  # Set sync source to channel 1
    device1.write(':OUTPut:SYNC:STATe ON')    # Enable sync output
    device1.write(':OUTPut:SYNC:MODE NORM')   # Normal sync mode
    
    # 2. Configure device2 to use external reference clock
    device2.write(':ROSCillator:SOURce EXTernal')  # External reference
    device2.write(':ROSCillator:EXTernal:FREQuency 10MHz')  # 10MHz reference
    
    # 3. Setup both devices to respond to trigger
    for device in [device1, device2]:
        device.write(':TRIGger:SOURce BUS')  # Set trigger source to software/bus
        device.write(':TRIGger:SLOPe POSitive')
        device.write(':TRIGger:DELay 0')
    
    # 4. Configure device1 to output trigger to device2
    device1.write(':TRIGger:OUTPut ON')
    
    # 5. Set up both devices to respond to the trigger
    for device in [device1, device2]:
        device.write(':INITiate:CONTinuous OFF')
        device.write(':INITiate:IMMediate')  # Arm the triggers
    
    print("Devices synchronized and armed. Ready to start together.")
    
    # Wait for devices to stabilize
    time.sleep(1)
    print("NOWWWWWW")
    time.sleep(3)
    
    # CRITICAL: Send the trigger to both devices simultaneously
    # This is the key to starting both devices at the exact same time
    device1.write('*TRG')
    device2.write('*TRG')
    
    # Turn on outputs
    for device in [device1, device2]:
        for i in [1, 2]:
            device.write(f':OUTPut{i}:STATe ON')
    
    print("Both devices started simultaneously.")
    
    # Return devices for later use if needed
    return device1, device2

# Example usage
device1_address = 'USB0::0x2A8D::0x8D01::CN64050190::0::INSTR'
device2_address = 'USB0::0x2A8D::0x8D01::CN64050101::0::INSTR'  # Replace with actual address

# Synchronize the devices
device1, device2 = sync_two_devices(device1_address, device2_address)
time.sleep(10)


#When done with the devices:
for device in [device1, device2]:
    for i in [1, 2]:
        device.write(f':OUTPut{i}:STATe OFF')
    device.close()