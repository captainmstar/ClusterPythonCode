import socket
import json
import time
import logging
import struct
import threading
from threading import Thread
# gHost needs to be "" for VR game or will throw gps error and loose socket connection
gHost = ""
gPort = 50021

logger = logging.getLogger(__name__)


class NetServer:
    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((gHost, gPort))
        self.s.listen(10)
        self.acceptthread = threading.Thread(target=self.acceptthreadproc, args=(self.s,)).start()
        # initialize list/set of all connected client's sockets
        self.client_threads = set()
        self.closed_threads = set()

    def close(self):
        print("NetServer close")
        for client_thread in self.client_threads:
            client_thread.close()
        self.s.close()

    def acceptthreadproc(self, s):
        while True:
            client_socket, addr = s.accept()
            print("client connect!" + addr[0] + ':' + str(addr[1]))
            # Create new thread to send CAN data messages to game
            client_thread = ClientThread(client_socket)
            client_thread.daemon = True
            client_thread.start()
            self.client_threads.add(client_thread)
            time.sleep(1.0)

    def send_message(self, message):
        # Check for any closed connections
        self.check_closed_threads()
        for client_thread in self.client_threads:
            try:
                client_thread.send(message)
            except BaseException as err:
                print("Removing client_thread")
                self.closed_threads.add(client_thread)

    def check_closed_threads(self):
        if len(self.closed_threads) > 0:
            for closed_thread in self.closed_threads:
                self.client_threads.remove(closed_thread)
            self.closed_threads.clear()


class Message:
    def __init__(self, duration, speed, acceleration, rpm, shifter_position, battery_voltage, battery_soc, battery_mode, battery_voltage_12v):
        self.duration = duration
        self.speed = speed
        self.acceleration = acceleration
        self.rpm = rpm
        self.shifter_position = shifter_position
        self.battery_voltage = battery_voltage
        self.battery_soc = battery_soc
        self.battery_mode = battery_mode
        self.battery_voltage_12v = battery_voltage_12v


class ClientThread(Thread):
    def __init__(self, conn):
        Thread.__init__(self)
        self.conn = conn

    def send(self, message: Message):
        if self.conn is not None:
            # Create json message to send
            jsonData = {"message": 1, "duration": message.duration, "speed": message.speed,
                        "acceleration": message.acceleration, "rpm": message.rpm,
                        "shifter_position": message.shifter_position, "battery_voltage": message.battery_voltage,
                        "battery_soc": message.battery_soc, "battery_mode": message.battery_mode, "battery_voltage_12v": message.battery_voltage_12v}
            jsonstr = json.dumps(jsonData).encode('ascii')
            # Setup message to send over socket
            msg_len = struct.pack('i', len(jsonstr))
            senddata = bytes()
            senddata += msg_len
            senddata += jsonstr
            try:
                self.conn.sendall(senddata)
            except BaseException as err:
                print("BaseException in send(): ", err)
                raise err
            print("sent message:", senddata)

    def close(self):
        print("ClientThread close")
        if self.conn is not None:
            self.conn.close()


if __name__ == "__main__":
    print('Initializing the Net...')

    net = NetServer()

    while True:
        time.sleep(1.0)

    net.Close()
