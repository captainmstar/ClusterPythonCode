"""
Interface for CAN data monitoring Runner and showing that on the cluster 
@author Kasra <kasramokhtari@indiev.com>
"""
from collections import deque
import can
import cantools
import time
import threading
from os import path
import math
import csv
import time
from multiprocessing import Process
from apscheduler.schedulers.background import BackgroundScheduler
from NetServer import NetServer
from NetServer import Message
import pandas as pd
import struct

# Defines the paths to the dbc files for different electric components (FrontEDU, Shifter, and BMS)
path_to_dbc_FrontEDU = path.abspath(path.join(path.dirname(__file__), 'dbc', 'CANcommunicationProtocol_V1.7_20200803.dbc'))
path_to_dbc_Shifter = path.abspath(path.join(path.dirname(__file__), 'dbc', 'Arens.dbc'))
path_to_dbc_BMS = path.abspath(path.join(path.dirname(__file__), 'dbc', 'INDI_BMS_v2.dbc'))

# Defines the can interface we are using:
vectorInterface = True
kvaserInterface = False

# Defines the parameter the vehicle paramters
gearRatio = 10.2
wheelsDiameter = 744 * 0.001  # in meter

lock = threading.Lock()

TEST = False


class SendCANThread(threading.Thread):
    # Creates an instance (instrument) of a CAN data Reader
    def __init__(self, instrument):
        threading.Thread.__init__(self)
        self.instrument = instrument


class Cluster(can.Listener):
    currentTime = time.time()
    last_time = time.time()
    last_speed = 0.0

    # Creates an instance of a cluster 
    def __init__(self, channel, gearRatio, wheelsDiameter, net: NetServer):
        # Defines the can interface that we are using
        if not TEST:
            self.bus = can.interface.Bus(bustype='vector', channel='1', bitrate=500000)
            #self.bus = can.interface.Bus(bustype='kvaser', channel='0', bitrate=500000)
            print('Connected to the CAN successfully!')
            # Reads the dbc files using Pyhton CAN library
            self.db_FrontEDU = cantools.database.load_file(path_to_dbc_FrontEDU)
            self.db_Shifter = cantools.database.load_file(path_to_dbc_Shifter)
            self.db_BMS = cantools.database.load_file(path_to_dbc_BMS)
            self.notifier = can.Notifier(self.bus, [self])
        self.threadActive = True
        self.RPM = 0
        self.vehicleSpeed = 0
        self.shifter = 0
        self.batteryVoltage = 0
        self.batterySOC = 0
        self.batteryMode = 'DisConnected'
        self.gearRatio = 10.2
        self.wheelsDiameter = 744 * 0.001  # in meter
        self.net_server = net  # socket connection to VR game and cluster
        self.shifterprev = 'P'

    def start(self):
        # Starts the Clsuer
        self.xmitThread = SendCANThread(self)
        self.xmitThread.start()

    def stop(self):
        # Ends the cluster session
        print("Stopping Cluster monitoring data")
        self.threadActive = False
        self.xmitThread.join()

    def on_message_received(self, msg: can.Message):
        # Runs this section everytime CAN receives new data (Called when a message on the bus is received)
        #print(msg)
        if msg.arbitration_id == int('0x121', 16):
            message_FrontEDU = self.db_FrontEDU.get_message_by_frame_id(msg.arbitration_id)
            ActRotSpd = message_FrontEDU.decode(msg.data)['MCU_ActRotSpd']
            MCU_StMode = message_FrontEDU.decode(msg.data)['MCU_StMode']
            MCU_ActTorq = message_FrontEDU.decode(msg.data)['MCU_ActTorq']
            MCU_General_ctRoll = message_FrontEDU.decode(msg.data)['MCU_General_ctRoll']
            self.RPM = ActRotSpd
            self.vehicleSpeed = ((ActRotSpd * 3.6 * math.pi * wheelsDiameter) / (gearRatio * 60)) * (0.621371)

        if msg.arbitration_id == int('0xC010305', 16):
            message_Shifter = self.db_Shifter.get_message_by_frame_id(msg.arbitration_id)
            Shifter_dbc = message_Shifter.decode(msg.data)['Shift_Req']
            if Shifter_dbc != "idel":
                self.shifter = Shifter_dbc
                self.shifterprev = Shifter_dbc
            else:
                self.shifter = self.shifterprev

        if msg.arbitration_id == int('0x821', 16):
            message_BMS = self.db_BMS.get_message_by_frame_id(msg.arbitration_id)
            Voltage = message_BMS.decode(msg.data)['BatteryPackVoltage']
            self.batteryVoltage = Voltage

        if msg.arbitration_id == int('0x821', 16):
            message_BMS = self.db_BMS.get_message_by_frame_id(msg.arbitration_id)
            BMS_Mode = message_BMS.decode(msg.data)['BMS_Mode']
            self.batteryMode = BMS_Mode

        if msg.arbitration_id == int('0x822', 16):
            message_BMS = self.db_BMS.get_message_by_frame_id(msg.arbitration_id)
            SOC = message_BMS.decode(msg.data)['SOC']
            self.batterySOC = SOC

    def startLog(self):
        header = ['Time', 'RPM', 'vehicleSpeed', 'shifter', 'batteryVoltage', 'batterySOC', 'batteryMode']
        # Defines name of csv file 
        self.filename = "clusterLogger.csv"

        # writing to csv file 
        with open(self.filename, 'w', newline='') as csvfile:
            # Creates a csv writer object 
            self.csvwriter = csv.writer(csvfile)
            # Writes the fields 
            self.csvwriter.writerow(header)

    def updatelog(self):
        # Writes the data rows
        data = [time.time() - self.currentTime, self.RPM, self.vehicleSpeed, self.shifter, self.batteryVoltage,
                self.batterySOC, self.batteryMode]
        with open(self.filename, 'a', newline='') as csvfile:
            self.csvwriter = csv.writer(csvfile)
            self.csvwriter.writerow(data)
        # Send CAN message to VR game and cluster via socket
        self.send_can_message()

    def send_can_message(self):
        duration = time.time() - self.last_time
        acceleration = get_acceleration(self.last_speed, self.vehicleSpeed, duration)
        if not TEST:
            message = Message(duration, self.vehicleSpeed, acceleration, self.RPM, self.shifter.name, self.batteryVoltage, self.batterySOC, self.batteryMode.name)
        else:
            message = Message(duration, self.vehicleSpeed, acceleration, self.RPM, self.shifter,
                              self.batteryVoltage, self.batterySOC, self.batteryMode)
        print(message)
        self.net_server.send_message(message)
        # Set last_time to now and last speed
        self.last_time = time.time()
        self.last_speed = self.vehicleSpeed

    def updatelog_test(self):
        # Read test data from 1 lap
        df = pd.read_csv('OneLapTest.csv')

        last_time = 0.0
        last_speed = 0.0

        try:
            for index, row in df.iterrows():
                # relative time from start of CAN bus
                rel_time = row["Time (rel)"]
                # speed of vehicle in kph
                speed = row["IprVehSpdKph"]
                rpm = row["CAN1.MCU_General.MCU_ActRotSpd"]
                shifter_position = row["ShcGearAct"]
                battery_voltage = row["BmnBatteryVoltage"]
                battery_soc = row["IprBattSoc"]
                battery_mode = row["CAN1.BCU_DEBUG.BMS_Mode"]
                # duration is how long vehicle has been traveling at this speed
                duration = rel_time - last_time
                last_time = rel_time
                # calculate acceleration
                acceleration = get_acceleration(last_speed, speed, duration)
                self.vehicleSpeed = speed
                self.RPM = rpm
                self.shifter = shifter_position
                self.batteryVoltage = battery_voltage
                self.batterySOC = battery_soc
                self.batteryMode = battery_mode
                self.send_can_message()
                # sleep for duration to simulate time delay of real CAN message
                time.sleep(duration)
        except Exception as e:
            print("Unexpected exception: " + e.message)


# acceleration = delta kph / delta hours
def get_acceleration(old_speed, new_speed, delta_seconds):
    delta_velocity = abs(new_speed - old_speed)
    delta_time = delta_seconds / 3600
    return delta_velocity / delta_time


if __name__ == "__main__":
    print('Initializing the NetServer...')
    net_server = NetServer()
    print('Initializing the Cluster...')
    clusterRunner = Cluster(0, gearRatio, wheelsDiameter, net_server)
    clusterRunner.start()
    clusterRunner.startLog()
    if not TEST:
        sched = BackgroundScheduler()
        # Logs the data every 10 seconds
        sched.add_job(clusterRunner.updatelog, 'interval', seconds=0.5)
        sched.start()
        print('Data is been logged into a csv file...')
    else:
        clusterRunner.updatelog_test()
    while True:
        time.sleep(1.0)
    # Shut down server if this is killed
    net_server.close()
