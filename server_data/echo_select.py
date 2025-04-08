#!/usr/bin/python3

import socket
import sys
import select

HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 8000               # Arbitrary non-privileged port

server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# overall timeout
server_sock.setblocking(False)
server_sock.bind((HOST, PORT))
server_sock.listen()

# list of current clients
myClients = []

while True:
    try:
        #block!
        readable, writable, error = select.select(
                    [server_sock, ] + myClients, [], [])

        for aSocket in readable:
            if aSocket == server_sock:
                conn, addr = server_sock.accept()
                print('Connected by', addr)
                # I can set a timeout here, for the client socket, too.
                conn.setblocking(False)
                myClients.append(conn)
        
            else: # must be in a client socket
                data = aSocket.recv(1024)
                asText = data.decode('utf-8')
                # is it done?
                if len(data) == 0:
                    myClients.remove(aSocket)
                    aSocket.close()
                elif asText.strip() == "exit":
                    # also close
                    myClients.remove(aSocket)
                    aSocket.close()
                else:
                    # send to everyone
                    for c in myClients:
                        c.sendall(data)

                    # pretty print 
                    # json.dumps(myObj, indent=2)
    except socket.timeout as e:
        #print('timeout')
        pass
    except KeyboardInterrupt as e:
        print("RIP")
        server_sock.close()
        sys.exit(0)
    except Exception as e:
        print("Something happened... I guess...")
        print(e)

