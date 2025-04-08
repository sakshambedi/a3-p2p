#!/usr/bin/python3

# from https://docs.python.org/3/howto/sockets.html#non-blocking-sockets
# and
# https://docs.python.org/3/library/socket.html#example

# Test with
# start listener nc -l -u 127.0.0.42422
# send
# cat testfile.json |  nc -u 127.0.0.1 4242


import json
import socket
import time

serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# bind the socket to a public host, and a well-known port
hostname = socket.gethostname()
print("listening on interface " + hostname)
# This accepts a tuple...
serversocket.bind(('', 42424))
count = 0

with serversocket: # this is a socket! With syntax does not work on python 2
    while True:

        try:
            #print('Connected by', addr)
            print("Blocking read...")
            data, addr  = serversocket.recvfrom(2048)
            print("out of block")

            print("got {} from {}".format(data, addr))
            asStr = data.decode('utf-8')
            out = "You said: >{}<".format(asStr)
            serversocket.sendto(out.encode(), addr)
        except Exception as e:
            print("general exception")
            print(e)
