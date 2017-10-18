import sys
import json
import multiprocessing as mp
import redfish
import requests
import re
import threading
import time
import urllib3
import Queue

urllib3.disable_warnings()

class SMCRedfish:
    def __init__(self, host="", user="ADMIN", pwd="ADMIN"):
        self.default_prefix="/redfish/v1"
        #self.rf_obj=redfish.redfish_client(base_url=host,username=user,password=pwd,default_prefix=self.default_prefix)
        self.host=host
        self.user=user
        self.pwd=pwd
        self.rf_obj=None
        self.rf_response=None
    def redfish_login(self):
        self.rf_obj=redfish.redfish_client(base_url=self.host,username=self.user,password=self.pwd,default_prefix=self.default_prefix)
        self.rf_obj.login(auth="session")
    def redfish_logout(self):
        self.rf_obj.logout()
    def redfish_get(self, link):
        str_link=self.default_prefix+link
        self.rf_response=self.rf_obj.get(str_link, None)
    def redfish_put(self):
        pass
    def redfish_post(self):
        pass
    def getBodyDict(self):
        return self.rf_response.dict
    def getStatus(self):
        return self.rf_response.status
    def getHost(self):
        return self.host
class SMCRedfishGPU:
    def __init__(self):
        self.rf_obj=None
        self.body=None
    def setRedfishObj(self, obj):
        self.rf_obj=obj
    def getRedfishObj(self):
        return self.rf_obj
    def getFormattedSEL(self):
        self.rf_obj.redfish_get("/Chassis/1/Thermal")
        self.data=self.rf_obj.getBodyDict()
        ret_val=""
        for item in self.data['Temperatures']:
            name=item['Name']
            regexp=re.compile(r'GPU[0-9] Temp')
            if regexp.search(name):
                #sys.stdout.write(item['MemberID']+':')
                #ret_val=ret_val+item['MemberID']+'|'
                ret_val=ret_val+item['Name'].split()[0]+':'+ str(item['ReadingCelsius'])+'|'
        return ret_val
    def getFormattedSEL_Thread(self, queue):
        output=""
        gpu_ids=self.getFormattedSEL()
        ip_str=self.getRedfishObj().getHost().split('/')[-1]
        output="Thermal(%-14s): %s \n" % (ip_str,gpu_ids)
        queue.put(output)
class SMCPostCodeSnoop:
    def __init__(self):
        self.rf_obj=None
    def setRedfishObj(self, obj):
        self.rf_obj=obj
    def getCurPostcode(self):
        self.rf_obj.redfish_get("/Managers/1/Snooping")
        dict=self.rf_obj.getBodyDict()
        return dict['PostCode']
    def getRedfishObj(self):
        return self.rf_obj
class SMCGPUMonitor:
    def __init__(self):
        self.state=0
        self._running=True
        self.gpu_obj=[]
        self.post_obj=[]
        self.obj=None
    def check_network(self, host="http://www.google.com"):
        sys.stdout.write("Checking network connection to %s...." % host)
        sys.stdout.flush()
        try:
            #r=requests.get("http://172.31.0.8", verify=False, timeout=10)
            #r=requests.get("http://www.google.com", verify=False, timeout=10)
            r=requests.get(host, verify=False, timeout=10)
            sys.stdout.write("OK\n")
            sys.stdout.flush()
            return True
        except requests.Timeout as err:
            sys.stdout.write("FAIL\n")
            sys.stdout.flush()
            return False
    def on_init(self):
        smc_sut=[]
        with open('ipmi-sut.txt','r') as ip_file:
            smc_sut= ['https://'+smc_sut.strip() for smc_sut in ip_file]
        for x in range(0, len(smc_sut)):
            obj=SMCRedfishGPU()
            obj2=SMCPostCodeSnoop()
            rf=SMCRedfish(smc_sut[x])
            #rf.redfish_login()
            obj.setRedfishObj(rf)
            obj2.setRedfishObj(rf)
            self.gpu_obj.append(obj)
            self.post_obj.append(obj2)
    def on_login(self):
        #for obj in self.gpu_obj:
        #    obj.getRedfishObj().redfish_login()
        tmp_threads=[]
        for obj in self.gpu_obj:
            rf_obj=obj.getRedfishObj()
            new_thread=threading.Thread(target=rf_obj.redfish_login, name='Thread-'+rf_obj.getHost())
            tmp_threads.append(new_thread)
            new_thread.start()
        for t in tmp_threads:
            t.join()
    def on_logout(self):
        #for obj in self.gpu_obj:
        #    obj.getRedfishObj().redfish_logout()
        tmp_threads=[]
        for obj in self.gpu_obj:
            rf_obj=obj.getRedfishObj()
            new_thread=threading.Thread(target=rf_obj.redfish_logout, name='Thread-'+rf_obj.getHost())
            tmp_threads.append(new_thread)
            new_thread.start()
        for t in tmp_threads:
            t.join()
    def on_monitor(self):
        #output=[]
        #try:
        #    for obj in self.gpu_obj:
        #        gpu_ids=obj.getFormattedSEL()
        #        ip_str=obj.getRedfishObj().getHost().split('/')[-1]
        #        output.append("Thermal(%-14s): %s \n" % (ip_str,gpu_ids))
        #    for i in output:
        #        sys.stdout.write(i)
        #    sys.stdout.flush()
            #for j in range(0,len(output)):
            #    sys.stdout.write("\033[F")
        #    sys.stdout.write('\n')
        #    sys.stdout.flush()
        #    time.sleep(1)
        #except(KeyboardInterrupt,SystemExit):
        #    print("Pressed Ctrl+C")
        #    self.state=-1            
        tmp_threads=[]
        output_queue=Queue.PriorityQueue()
        try:
            for obj in self.gpu_obj:
                new_thread=threading.Thread(target=obj.getFormattedSEL_Thread, args=[output_queue])
                tmp_threads.append(new_thread)
                new_thread.start()
            for t in tmp_threads:
                t.join()
            while not output_queue.empty():
                sys.stdout.write(output_queue.get())
            sys.stdout.write('\n')
            sys.stdout.flush()
            time.sleep(1)
        except(KeyboardInterrupt,SystemExit):
            print("Pressed Ctrl+C")
            self.state=-1
        sys.stdout.flush()
    def on_execute(self):
        while(self._running):
            if(self.state==0):
                #state#1: initialization
                self.on_init()
                self.state=1
            elif(self.state==1):
                #state#2: Chekcing network connection
                self.state=2
                ret=self.check_network()
                if not ret:
                    #print("Timeout, exit")
                    sys.stdout.write("Timeout, exit\n")
                    sys.stdout.flush()
                    self.state=-1
                for obj in self.gpu_obj:
                    ret=self.check_network(obj.getRedfishObj().getHost())
            elif(self.state==2):
                #State#3: Login
                self.on_login()
                self.state=3
            elif(self.state==3):
                #State#4: Start monitoring
                #output=[]
                #try:
                #    for obj in self.post_obj:
                #        postcode=obj.getCurPostcode()
                #        ip_str=obj.getRedfishObj().getHost()
                #        #sys.stdout.write("Postcode(%s): %s \n" % (ip_str,postcode))
                #        output.append("Postcode(%s): %s \n" % (ip_str,postcode))
                #    for i in output:
                #        sys.stdout.write(i)
                #    sys.stdout.flush()
                #    for j in range(0,len(output)):
                #        sys.stdout.write("\033[F")
                #    sys.stdout.flush()
                #    time.sleep(1)
                #except(KeyboardInterrupt,SystemExit):
                #    print("Pressed Ctrl+C")
                #    self.state=-1
                ######################################
                cur_time=time.time()
                self.on_monitor()
                cost_time=time.time()-cur_time
                sys.stdout.write('Used Time(secs): %f\n' % cost_time)
                sys.stdout.flush()
            elif(self.state==-1):
                #State#End: Exiting
                self._running=False
                self.on_logout()
            else:
                #print("Unexpected State: Exit")
                print "Unexpected State: Exit"
                self._running=False     
if __name__=="__main__":
    GPUMoniter=SMCGPUMonitor()
    GPUMoniter.on_execute()
    #App = SMCRedfish('https://172.29.183.76')
    #App.redfish_login()
    #App.redfish_get('/Chassis/1/Thermal')
    #obj=App.getBodyDict()
    #for item in obj['Temperatures']:
    #    name=item['Name']
    #    regexp=re.compile(r'GPU[0-9] Temp')
    #    if regexp.search(name):
    #            sys.stdout.write(item['MemberID'])
    #           sys.stdout.write('\n')
    #App.redfish_logout()