import socket
import json
import time
import logging
import struct
import threading
from threading import Thread

gHost = "localhost"
gPort = 50021

logger = logging.getLogger(__name__)


class NetServer:
    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((gHost, gPort))
        self.s.listen(10)
        self.acceptthread = threading.Thread(target=self.acceptthreadproc, args=(self.s, self,)).start()
        self.client_thread = None
        pass

    def Close(self):
        self.s.close()

    def acceptthreadproc(self, s, netserver):
        while True:
            conn, addr = s.accept()
            print("client connect!")
            # Create new thread to send CAN data messages to game
            self.client_thread = ClientThread(conn)
            self.client_thread.start()
            # threading.Thread(target=self.clientthread, args=(conn, netserver,)).start()
            time.sleep(1.0)

    def send_message(self, message):
        if self.client_thread is not None:
            self.client_thread.send(message)


class Message:
    def __init__(self, duration, speed, acceleration):
        self.duration = duration
        self.speed = speed
        self.acceleration = acceleration


class ClientThread(Thread):
    def __init__(self, conn):
        Thread.__init__(self)
        self.conn = conn

    def send(self, message: Message):
        if self.conn is not None:
            # Create json message to send
            jsonData = {"message": 1, "duration": message.duration, "speed": message.speed,
                        "acceleration": message.acceleration}
            jsonstr = json.dumps(jsonData).encode('ascii')
            # Setup message to send over socket
            msg_len = struct.pack('i', len(jsonstr))
            senddata = bytes()
            senddata += msg_len
            senddata += jsonstr
            try:
                self.conn.sendall(senddata)
            except BaseException as err:
                print("BaseException in run(): ", err.message)
            print("sent message:", senddata)


if __name__ == "__main__":
    print('Initializing the Net...')

    net = NetServer()

    while True:
        time.sleep(1.0)

    net.Close()
