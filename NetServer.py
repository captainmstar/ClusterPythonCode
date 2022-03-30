import socket
import json
import sys
import time
import logging
import struct
import threading
from threading import Thread
from warnings import catch_warnings
import pandas as pd
from Cluster_DataMonitoring_Runner_03242022 import Cluster

gHost = ""
gPort = 50021

logger = logging.getLogger(__name__)


class NetServer():
    def __init__(self, cluster: Cluster):
        self.cluster = cluster
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((gHost, gPort))
        self.s.listen(10)
        self.conn = None

        self.acceptthread = threading.Thread(target=self.acceptthreadproc, args=(self.s, self,)).start()
        pass

    def Close(self):
        self.s.close()

    def acceptthreadproc(self, s, netserver):
        while True:
            conn, addr = s.accept()
            print("client connect!")
            self.conn = conn
            threading.Thread(target=self.clientthread, args=(conn, netserver,)).start()
            time.sleep(1.0)

    # acceleration = delta kph / delta hours
    def get_acceleration(old_speed, new_speed, delta_seconds):
        delta_velocity = abs(new_speed - old_speed)
        delta_time = delta_seconds / 3600
        return delta_velocity / delta_time

    def sendData(self, duration, speed):
        if self.conn is not None:
            # Create json message to send
            jsonData = {"message": 1, "duration": self.cluster.duration, "speed": self.cluster.vehicleSpeed,
                        "acceleration": acceleration}
            jsonstr = json.dumps(jsonData).encode('ascii')
            # Setup message to send over socket
            msg_len = struct.pack('i', len(jsonstr))
            senddata = bytes()
            senddata += msg_len
            senddata += jsonstr
            try:
                self.conn.sendall(senddata)
            except BaseException as err:
                break
            print("sent message:", senddata)


    def clientthread(self, conn, netserver):
        # df = pd.read_csv('OneLapTest.csv')
        # last_time = 0.0
        # last_speed = 0.0
        # for index, row in df.iterrows():
        #     # relative time from start of CAN bus
        #     rel_time = row["Time (rel)"]
        #     # speed of vehicle in kph
        #     speed = row["IprVehSpdKph"]
        #     # duration is how long vehicle has been traveling at this speed
        #     duration = rel_time - last_time
        #     last_time = rel_time
        #     # calculate acceleration
        #     acceleration = self.get_acceleration(last_speed, speed, duration)
        #     # Create json message to send
        #     jsonData = {"message": 1, "duration": duration, "speed": speed, "acceleration": acceleration}
        #     jsonstr = json.dumps(jsonData).encode('ascii')
        #     # Setup message to send over socket
        #     msg_len = struct.pack('i', len(jsonstr))
        #     senddata = bytes()
        #     senddata += msg_len
        #     senddata += jsonstr
        #     try:
        #         conn.sendall(senddata)
        #     except BaseException as err:
        #         break
        #     print("sent message:", senddata)
        #     # sleep for duration to simulate time delay of real CAN message
        #     time.sleep(duration)
        while True:
            #Create json message to send
            jsonData = {"message": 1, "duration": self.cluster.duration, "speed": self.cluster.vehicleSpeed, "acceleration": acceleration}
            jsonstr = json.dumps(jsonData).encode('ascii')
            # Setup message to send over socket
            msg_len = struct.pack('i', len(jsonstr))
            senddata = bytes()
            senddata += msg_len
            senddata += jsonstr
            try:
                conn.sendall(senddata)
            except BaseException as err:
                break
            print("sent message:", senddata)
        conn.close()
        print("client close!")


class CANMessage(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):


if __name__ == "__main__":
    print('Initializing the Net...')

    net = NetServer()

    while True:
        time.sleep(1.0)

    net.Close()
