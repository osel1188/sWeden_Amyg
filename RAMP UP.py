#RAMP UP 




start = 0 #mv
duration = 60 # seconds
import time

# def ramp(float* maxAmplitude):

#     step[4] = {};
#     currentVoltage[4] = {};

#     numberOf100msTimeSteps = duration * 10;

#     for(i=0; i<4; i++){
#         step[i] = maxAmplitude[i]/numberOf100msTimeSteps;
#     }

#     for(i=0; i < numberOf100msTimeSteps; i++){
#         for(i=0; i<4; i++){
#         currentVoltage[i] += step[i];
#         set_voltage(i, currentVoltage[i]);
#         }
#         delay(100 ms);
#     }


def ramp( maxAmplitude,duration):

    step = [0,0,0,0] 
    currentVoltage = [0,0,0,0]

    numberOf100msTimeSteps = duration * 10


    for i in range(0,len(step)):
   
        step[i] = maxAmplitude[i]/numberOf100msTimeSteps
    

    for i in range(0,numberOf100msTimeSteps):
        for j in range(0,len(step)):
                
            currentVoltage[j] += step[j]

            print(currentVoltage[j])
            #set_voltage(i, currentVoltage[i]);
      
        time.sleep(0.1)


ramp([1,1,1,1],60)