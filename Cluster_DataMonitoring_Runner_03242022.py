"""
Interface for CAN data monitoring Runner and showing that on the cluster 
@author Kasra <kasramokhtari@indiev.com>
"""
import can
import cantools
import threading
from os import path
import math
import csv
import time
from apscheduler.schedulers.background import BackgroundScheduler
from queue import SimpleQueue, Empty
from typing import Any, AsyncIterator, Awaitable, Optional
from can.message import Message
from NetServer import NetServer
from NetServer import Message
import pandas as pd

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
currentTime = time.time()

lock = threading.Lock()

TEST = True


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
    def __init__(self, net: NetServer):
        # Defines the can interface that we are using
        if not TEST:
            # self.bus = can.ThreadSafeBus(bustype='kvaser', channel='0', bitrate=500000)
            self.bus = can.ThreadSafeBus(bustype='vector', channel='1', bitrate=500000)
            print('Connected to the CAN successfully!')
            self.buffer: SimpleQueue[Message] = SimpleQueue()
            self.is_stopped = False
            # Reads the dbc files using Pyhton CAN library
            self.db_FrontEDU = cantools.database.load_file(path_to_dbc_FrontEDU)
            self.db_Shifter = cantools.database.load_file(path_to_dbc_Shifter)
            self.db_BMS = cantools.database.load_file(path_to_dbc_BMS)
            self.notifier = can.Notifier(self.bus, [self])
        self.threadActive = True
        self.RPM = 0
        self.vehicleSpeed = 0
        self.shifter = 'P'
        self.batteryVoltage = 0
        self.batterySOC = 0
        self.batteryMode = 'DisConnected'
        self.gearRatio = 10.2
        self.wheelsDiameter = 744 * 0.001  # in meter
        self.shifterReq = 'P'
        self.net_server = net  # socket connection to VR game and cluster

    def start(self):
        # Starts the Clsuer
        self.xmitThread = SendCANThread(self)
        self.xmitThread.start()

    def stop(self):
        # Ends the cluster session
        """Prohibits any more additions to this reader."""
        self.is_stopped = True
        print("Stopping Cluster monitoring data")
        self.threadActive = False
        self.xmitThread.join()

    def on_message_received(self, msg: can.Message):
        # Runs this section everytime CAN receives new data (Called when a message on the bus is received)
        """Append a message to the buffer.

                :raises: BufferError
                    if the reader has already been stopped
                """
        '''
        if self.is_stopped:
            raise RuntimeError("reader has already been stopped")
        else:
            self.buffer.put(msg)
        '''
        try:
            if msg.arbitration_id == int('0x121', 16):
                message_FrontEDU = self.db_FrontEDU.get_message_by_frame_id(msg.arbitration_id)
                ActRotSpd = message_FrontEDU.decode(msg.data)['MCU_ActRotSpd']
                MCU_StMode = message_FrontEDU.decode(msg.data)['MCU_StMode']
                MCU_ActTorq = message_FrontEDU.decode(msg.data)['MCU_ActTorq']
                MCU_General_ctRoll = message_FrontEDU.decode(msg.data)['MCU_General_ctRoll']
                self.RPM = ActRotSpd
                self.vehicleSpeed = ((ActRotSpd * 3.6 * math.pi * wheelsDiameter) / (gearRatio * 60)) * (0.621371)

            if msg.arbitration_id == int('0xc010305', 16):
                message_Shifter = self.db_Shifter.get_message_by_frame_id(msg.arbitration_id)
                Shifter_dbc = message_Shifter.decode(msg.data)['Shift_Req']
                if Shifter_dbc != 'Idel':
                    self.shifterReq = Shifter_dbc

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
        except Exception as e:
            print("Exception thrown in on_message_received: ", e)

    def get_message(self, timeout: float = 2.0) -> Optional[Message]:
        """
        Attempts to retrieve the latest message received by the instance. If no message is
        available it blocks for given timeout or until a message is received, or else
        returns None (whichever is shorter). This method does not block after
        :meth:`can.BufferedReader.stop` has been called.

        :param timeout: The number of seconds to wait for a new message.
        :return: the Message if there is one, or None if there is not.
        """

        try:
            pass
        except Empty:
            print('--------------------------------------------------------------------')
            print('------------------------Reinitiating CAN----------------------------')
            # self.bus = can.ThreadSafeBus(bustype='kvaser', channel='0', bitrate=500000)
            self.bus = can.ThreadSafeBus(bustype='vector', channel='1', bitrate=500000)
            print('-----------------CAN Connection is reestablished--------------------')
            print('--------------------------------------------------------------------')
            return None

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
        data = [time.time() - currentTime, self.RPM, self.vehicleSpeed, self.shifterReq, self.batteryVoltage,
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
            msg = Message(duration, self.vehicleSpeed, acceleration, self.RPM, self.shifterReq, self.batteryVoltage, self.batterySOC, self.batteryMode.name)
        else:
            msg = Message(duration, self.vehicleSpeed, acceleration, self.RPM, self.shifterReq,
                          self.batteryVoltage, self.batterySOC, self.batteryMode)
        # print(message)
        self.net_server.send_message(msg)
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
    clusterRunner = Cluster(net_server)
    clusterRunner.start()
    clusterRunner.startLog()
    if not TEST:
        sched = BackgroundScheduler()
        # Logs the data every 10 seconds
        sched.add_job(clusterRunner.updatelog, 'interval', seconds=0.5)
        sched.start()
        print('Data is been logged into a csv file...')
        time.sleep(1.0)
    else:
        clusterRunner.updatelog_test()
    while True:
        clusterRunner.get_message()
        time.sleep(1.0)
    # Shut down server if this is killed
    net_server.close()
