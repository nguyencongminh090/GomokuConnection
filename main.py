import socket
import time
from queue import Queue
from threading import Thread
import re


class Singleton(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Singleton, cls).__new__(cls)
        return cls.instance


class Server:
    def __init__(self, host: str, port: int):
        self.__host = host
        self.__port = port
        self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SOCKET.bind((self.__host, self.__port))
        self.SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.SOCKET.listen()

        self.__listClient = {}
        self.__clientPermission = {}

        self.commandTask = Queue()
        self.BOARD = Board(19, 15)

        self.STATE = 1
        self.GAME_STATE = 0
        self.player_1 = None
        self.player_2 = None
        Thread(target=self.handleCommand, daemon=True).start()
        Thread(target=self.acceptClientConnection, daemon=True).start()

    def broadcast(self, message: str, _from=None, _to=None, timeout=0.0):
        print(f'[BROADCAST] {message} {_from} {_to}')
        exceptionClient = []
        if _to:
            try:
                self.__listClient[_to].send(message.encode())
            except:
                exceptionClient.append(_to)
        else:
            for client in self.__listClient:
                try:
                    if client != _from:
                        self.__listClient[client].send(message.encode())
                        # print(f'--> BROADCAST to {client}: {message}')
                except:
                    exceptionClient.append(client)
                    continue
        for client in exceptionClient:
            del self.__listClient[client]
            del self.__clientPermission[client]
            if self.player_1 == client:
                self.player_1 = None
                self.checkGameState()
                self.broadcast('<detach_player_1>')
            elif self.player_2 == client:
                self.player_2 = None
                self.checkGameState()
                self.broadcast('<detach_player_2>')

        time.sleep(timeout)

    def checkGameState(self):
        if self.player_1 and self.player_2:
            self.GAME_STATE = 1
        else:
            self.GAME_STATE = 0

    def handleClientConnection(self, client):
        def commandType(string):
            if re.match('^@', string):
                return 0
            elif re.match('^<#(.*?)>$', string):
                return 1
            else:
                return 2

        def getCommand(string):
            return re.match('^<#(.*?)>$', string).group(1)

        def getPeople(string):
            return re.match(r'^@(\w*)', string).group(1), re.split(r'^@\w*', string)[1].strip()

        def playerLeave():
            print(f'-> {name} had just left')
            client.detach()
            self.broadcast(f'[SERVER] {name} had just left')

        # Check name
        name = '_'.join(client.recv(1024).decode().split())

        self.broadcast(f'{name} has joined')
        print(f'{name} has joined')
        # Broadcast player
        self.__listClient[name] = client
        self.__clientPermission[name] = 0

        for idx, player in enumerate([self.player_1, self.player_2]):
            if player is not None:
                self.broadcast(f'<setplayer_{idx + 1} {player}>', _to=name)

        boardSize = self.BOARD.getBoardSize()
        self.broadcast(f'<setboard {boardSize[0]} {boardSize[1]}>', _to=name)

        while True:
            try:
                message = client.recv(1024).decode().strip()
                if message == '':
                    playerLeave()
                    break
            except:
                playerLeave()
                break

            print('<-', name, message)
            match commandType(message):
                case 0:
                    message = getPeople(message)
                    self.broadcast(message[1], _from=name, _to=message[0])
                case 1:
                    print((getCommand(message), name))
                    self.commandTask.put((getCommand(message), name))
                case 2:
                    self.broadcast(f'{name}: {message}', _from=name)

        return

    def handleCommand(self):
        def isPlayer_1(_name):
            return _name == self.player_1

        def checkPermission(_name):
            return self.__clientPermission[_name]

        def waitResponse(_command, _name):
            if isPlayer_1(_name):
                opponent = self.player_2
            else:
                opponent = self.player_1
            self.broadcast(f'<ask Allow {_name} to {_command}?>', _to=opponent)
            while self.STATE:
                if self.commandTask.empty():
                    continue
                else:
                    _command = self.commandTask.get()
                    if _command[1] == _name:
                        self.broadcast('[SERVER] Permission denied', _to=_command[1])
                    return 1 if _command[0] == 'yes' else 0, opponent

        while self.STATE:
            if self.commandTask.empty():
                continue
            command = self.commandTask.get()
            match command[0].split():
                case ['clear']:
                    if self.GAME_STATE:
                        response = waitResponse(f'[clear]', command[1])
                        if not checkPermission(command[1]):
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast('[SERVER] Permission denied', _to=command[1])
                            continue
                        if response[0]:
                            self.broadcast('<yes>', _to=command[1])
                            self.BOARD.clear()
                            self.broadcast(f'<clear>')
                        else:
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast(f'[-] {response[1]} refused to [clear]')
                    else:
                        self.broadcast('<deny>', _to=command[1])
                        self.__listClient[command[1]].send('[SERVER] Wait player...'.encode())
                case ['add', coord]:
                    if self.GAME_STATE:
                        if not checkPermission(command[1]):
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast('[SERVER] Permission denied', _to=command[1])
                            continue
                        if self.BOARD.checkValid(coord):
                            self.broadcast('<yes>', _to=command[1])
                            self.BOARD.addMove(coord)
                            self.broadcast(f'<add {coord}>', _from=command[1])
                        else:
                            self.broadcast('<deny>', _to=command[1])
                    else:
                        self.broadcast('<deny>', _to=command[1])
                        self.__listClient[command[1]].send('[SERVER] Wait player...'.encode())
                case ['setboard', x, y]:
                    if self.GAME_STATE:
                        if not checkPermission(command[1]):
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast('[SERVER] Permission denied', _to=command[1])
                            continue
                        response = waitResponse(f'[set board {x}x{y}]', command[1])
                        if response[0]:
                            self.broadcast('<yes>', _to=command[1])
                            self.BOARD.setBoard(x, y)
                            self.BOARD.clear()
                            self.broadcast(f'<setboard {x} {y}>')
                        else:
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast(f'[-] {response[1]} refused to [set board {x}x{y}]')
                    else:
                        self.broadcast('<deny>', _to=command[1])
                        self.__listClient[command[1]].send('[SERVER] Wait player...'.encode())
                case ['undo']:
                    if self.GAME_STATE:
                        if not checkPermission(command[1]):
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast('[SERVER] Permission denied', _to=command[1])
                            continue
                        if self.BOARD.checkValid('undo'):
                            response = waitResponse('[undo]', command[1])
                            if response[0]:
                                self.broadcast('<yes>', _to=command[1])
                                self.broadcast('<undo>', _from=command[1])
                                self.BOARD.undo()
                            else:
                                self.broadcast('<deny>', _to=command[1])
                                self.broadcast(f'[-] {response[1]} refused to undo')
                        else:
                            self.broadcast('<deny>', _to=command[1])
                    else:
                        self.broadcast('<deny>', _to=command[1])
                        self.__listClient[command[1]].send('[SERVER] Wait player...'.encode())
                case ['redo']:
                    if self.GAME_STATE:
                        if not checkPermission(command[1]):
                            self.broadcast('<deny>', _to=command[1])
                            self.broadcast('[SERVER] Permission denied', _to=command[1])
                            continue
                        if self.BOARD.checkValid('redo'):
                            response = waitResponse('[redo]', command[1])
                            if response[0]:
                                self.broadcast('<yes>', _to=command[1])
                                self.broadcast('<redo>', _from=command[1])
                                self.BOARD.redo()
                            else:
                                self.broadcast('<deny>', _to=command[1])
                                self.broadcast(f'[-] {response[1]} refused to redo')
                        else:
                            self.broadcast('<deny>', _to=command[1])
                    else:
                        self.broadcast('<deny>', _to=command[1])
                        self.__listClient[command[1]].send('[SERVER] Wait player...'.encode())
                case ['setplayer_1']:
                    if checkPermission(command[1]) or self.player_1 is not None:
                        self.broadcast('<deny>', _to=command[1])
                        self.broadcast('[SERVER] Permission denied', _to=command[1])
                        continue
                    self.broadcast('<yes>', _to=command[1])

                    self.player_1 = command[1]
                    self.__clientPermission[command[1]] = 1
                    self.checkGameState()
                    self.broadcast(f'<setplayer_1 {command[1]}>', _from=command[1])
                case ['setplayer_2']:
                    if checkPermission(command[1]) or self.player_2 is not None:
                        self.broadcast('<deny>', _to=command[1])
                        self.broadcast('[SERVER] Permission denied', _to=command[1])
                        continue
                    self.broadcast('<yes>', _to=command[1])

                    self.player_2 = command[1]
                    self.__clientPermission[command[1]] = 1
                    self.checkGameState()
                    self.broadcast(f'<setplayer_2 {command[1]}>', _from=command[1])
                case ['detach_player_1']:
                    if self.player_1 != command[1]:
                        self.broadcast('<deny>', _to=command[1])
                        self.broadcast('[SERVER] Permission denied', _to=command[1])
                        continue
                    self.broadcast('<yes>', _to=command[1])

                    self.player_1 = None
                    self.__clientPermission[command[1]] = 0
                    self.checkGameState()
                    self.broadcast('<detach_player_1>')
                case ['detach_player_2']:
                    if self.player_2 != command[1]:
                        self.broadcast('<deny>', _to=command[1])
                        self.broadcast('[SERVER] Permission denied', _to=command[1])
                        continue
                    self.broadcast('<yes>', _to=command[1])

                    self.player_2 = None
                    self.__clientPermission[command[1]] = 0
                    self.checkGameState()
                    self.broadcast('<detach_player_2>')

    def interact(self):
        while self.STATE:
            msg = input('Type: ')
            match msg:
                case 'get_pos':
                    print('-> Position:', self.BOARD.getPosition())
                case 'board_size':
                    print('->', self.BOARD.getBoardSize())
                case 'player':
                    print('Players in room:')
                    for name in self.__listClient:
                        print('+', name)
                case 'player_playing':
                    print('#1', self.player_1)
                    print('#2', self.player_2)

    def acceptClientConnection(self):
        while True:
            client, address = self.SOCKET.accept()
            client.send('[SERVER] Welcome'.encode())
            Thread(target=self.handleClientConnection, args=(client,), daemon=True).start()


class Client:
    def __init__(self, host, port):
        self.__host = host
        self.__port = port
        self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SOCKET.connect((self.__host, self.__port))
        self.STATE = 1

        Thread(target=self.receive, daemon=True).start()
        Thread(target=self.interact, daemon=True).start()

    def receive(self):
        while self.STATE:
            message = self.SOCKET.recv(1024).decode().strip()
            print(message)

    def send(self, message):
        self.SOCKET.send(message.encode())

    def interact(self):
        name = input('Type your __name: ')
        self.send(name)
        while self.STATE:
            getInput = input('Message: ')
            self.send(getInput)


class Board:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.__listCoord = []
        self.__history = []

    def clear(self):
        self.__listCoord.clear()

    def addMove(self, move):
        # Type: (str,str)
        if self.__history and move != self.__history[-1]:
            self.__history.clear()
        self.__listCoord.append(move)

    def setBoard(self, x, y):
        self.w = int(x)
        self.h = int(y)

    def undo(self):
        self.__history.append(self.__listCoord.pop())

    def redo(self):
        self.__listCoord.append(self.__history.pop())

    def checkValid(self, action):
        match action:
            case 'undo':
                return self.__listCoord != []
            case 'redo':
                return self.__history != []
            case _:
                return action not in self.__listCoord

    def setPosition(self, pos):
        ...

    def getPosition(self):
        return getPositionFromList(self.__listCoord)

    def getBoardSize(self):
        return self.w, self.h


def getPositionFromList(listMove):
    string = ''
    for i in listMove:
        x = chr(97 + int(i.split(',')[0]))
        y = str(int(i.split(',')[1]) + 1)
        string += x + y
    return string


def main():
    host = input('Host: ')
    port = int(input('Port: '))
    Server(host, port).interact()


if __name__ == '__main__':
    main()
