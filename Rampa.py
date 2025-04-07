import time



def Rampa(Devs,chs,Vs):
    steps = list()
    r_time = int(60)
    for i in Vs:
        steps.append(i/r_time)
    amps = steps
    tim = 0
    print(steps)


    





    while tim <= r_time:
        
        print(Devs[0])
        print(f"Channel {chs[0]},, amp {amps[0]}")
        print(f"Channel {chs[1]},, amp {amps[1]}")
        amps[0] = amps[0]+ steps[0]
        print(f"steps{steps[0]}")
        amps[1] = amps[1] +steps[1]
        print(Devs[1])
        print(f"Channel {chs[2]},, amp {amps[2]}")
        print(f"Channel {chs[3]},, amp {amps[3]}")
        amps[2] = amps[2]+steps[2]
        amps[3] = amps[3] +steps[3]
            
        print('h',steps)
        time.sleep(1)
        tim+=1
        print(amps)
    

Rampa(["K1","K2"],[1,2,1,2],[1,1,1,1])