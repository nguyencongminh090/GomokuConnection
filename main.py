# Author: nguyencongminh090
# Github: <https://github.com/nguyencongminh090/GomokuConnection>

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

# Current version of the server has only one table
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
        self.BOARD = Board(15, 15)

        self.STATE = 1              # the server is running
        self.GAME_STATE = 0         # 0: waiting for player  1: playing game
        self.GAME_OPENING = True
        self.GAME_FIRST_PLAYER = 1  # the player who puts 3 rocks on opening
        self.GAME_TURN = 1          # the player who is currently permitted to do the next move
        self.player_1 = None        # name string of player 1
        self.player_2 = None        # name string of player 2
        
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
            output = re.match(r'@(\w+)\s(.+)', string)
            return output.group(1), output.group(2)

        def playerLeave():
            print(f'-> {name} had just left')
            client.detach()
            self.broadcast(f'[SERVER] {name} had just left')

        # Check name
        name = '_'.join(client.recv(1024).decode().split())
        if name in self.__listClient:
            name += time.strftime("%M%S")
        self.broadcast(f'{name} has joined')
        print(f'{name} has joined')
        
        # Broadcast player
        self.__listClient[name] = client
        self.__clientPermission[name] = 0

        for idx, player in enumerate([self.player_1, self.player_2]):
            if player is not None:
                self.broadcast(f'<setplayer_{idx + 1} {player}>', _to=name)
        
        if (self.GAME_STATE):
            self.broadcast(f'<turn {self.player_1 if self.GAME_TURN == 1 else self.player_2}>')
        
        boardSize = self.BOARD.getBoardSize()
        self.broadcast(f'<setboard {boardSize[0]} {boardSize[1]}>', _to=name)

        listMove = self.BOARD.getPosition()
        if listMove:
            self.broadcast(f'<setpos {listMove}>', _to=name)

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
                    self.broadcast(f'{name}: {message[1]}', _from=name, _to=message[0])
                case 1:
                    self.commandTask.put((getCommand(message), name))
                case 2:
                    self.broadcast(f'{name}: {message}', _from=name)

        return

    def handleCommand(self):
        def isPlayer_1(_name):
            return _name == self.player_1
        
        def playerNum(_name):
            num = 1 if isPlayer_1(_name) else 2
            return num

        def playerFromNum(num):
            player_name = self.player_1 if num == 1 else self.player_2
            return player_name
        
        def nextTurn(num):
            num_next = 1 if num == 2 else 2
            return num_next

        def newGame():
            self.BOARD.clear()
            self.GAME_OPENING = True
            self.GAME_FIRST_PLAYER = nextTurn(self.GAME_FIRST_PLAYER)
            self.GAME_TURN = self.GAME_FIRST_PLAYER
            broadcastTurn()

        def broadcastTurn():
            player_name = playerFromNum(self.GAME_TURN)
            self.broadcast(f'<turn {player_name}>')
        
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
                    time.sleep(0.01)
                    continue
                else:
                    _command = self.commandTask.get()
                    if _command[1] == _name:
                        self.broadcast('[SERVER] Permission denied', _to=_command[1])
                    return 1 if _command[0] == 'yes' else 0, opponent

        cmd_list_player = ['setplayer_1', 'setplayer_2', 'detach_player_1', 'detach_player_2']
        
        while self.STATE:
            if self.commandTask.empty():
                time.sleep(0.01)
                continue
            command = self.commandTask.get()

            cmd_seq = command[0].split()
            cmd_sender = command[1]
            
            if (cmd_seq[0] not in cmd_list_player):
                if not checkPermission(cmd_sender):
                    self.broadcast('<deny>', _to=cmd_sender)
                    self.broadcast('[SERVER] Permission denied', _to=cmd_sender)
                    continue
                if self.GAME_STATE == 0:
                    self.broadcast('<deny>', _to=cmd_sender)
                    self.__listClient[cmd_sender].send('[SERVER] Wait player...'.encode())
                    continue
            
            match cmd_seq:
                case ['clear']:
                    response = waitResponse(f'[clear]', cmd_sender)
                    if response[0]:
                        self.broadcast('<yes>', _to=cmd_sender)
                        self.broadcast(f'<clear>', _from=cmd_sender)
                        newGame()
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast(f'[-] {response[1]} refused to [clear]')
                
                case ['setboard', x, y]:
                    if (int(x) < 5 or int(y) < 5 or int(x) > 26 or int(y) > 26):
                        self.broadcast('<deny>', _to=cmd_sender)
                        continue

                    response = waitResponse(f'[set board {x}x{y}]', cmd_sender)
                    if response[0]:
                        self.broadcast('<yes>', _to=cmd_sender)
                        self.BOARD.setBoard(x, y)
                        self.broadcast(f'<setboard {x} {y}>', _from=cmd_sender)
                        newGame()
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast(f'[-] {response[1]} refused to [set board {x}x{y}]')

                case ['add', coord]:
                    if self.BOARD.checkValid(coord) and playerNum(cmd_sender) == self.GAME_TURN:
                        self.broadcast('<yes>', _to=cmd_sender)
                        self.BOARD.addMove(coord)
                        self.broadcast(f'<add {coord}>', _from=cmd_sender)

                        rec_len = self.BOARD.getRecordLen()

                        if self.GAME_OPENING:
                            if (rec_len < 3 or rec_len == 4):
                                continue
                            elif (rec_len == 6):
                                self.GAME_OPENING = False
                        
                        self.GAME_TURN = nextTurn(self.GAME_TURN)
                        broadcastTurn()
                        
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)

                case ['pass']:
                    rec_len = self.BOARD.getRecordLen()
                    
                    valid = False
                    if self.GAME_OPENING and playerNum(cmd_sender) == self.GAME_TURN:
                        if rec_len in [3, 4, 5]:
                            valid = True
                    
                    if valid:
                        self.broadcast('<yes>', _to=cmd_sender)
                        self.GAME_OPENING = False
                        self.GAME_TURN = nextTurn(self.GAME_TURN)
                        self.broadcast('<pass>', _from=cmd_sender)
                        broadcastTurn()
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast('[SERVER] Denied: pass command is for the Swap2 opening rule', _to=cmd_sender)
                    
                case ['undo']:
                    if self.GAME_OPENING == False and self.BOARD.checkValid('undo'):
                        response = waitResponse('[undo]', cmd_sender)
                        if response[0]:
                            self.broadcast('<yes>', _to=cmd_sender)
                            self.broadcast('<undo>', _from=cmd_sender)
                            self.BOARD.undo()
                        else:
                            self.broadcast('<deny>', _to=cmd_sender)
                            self.broadcast(f'[-] {response[1]} refused to undo')
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)

                case ['redo']:
                    if self.GAME_OPENING == False and self.BOARD.checkValid('redo'):
                        response = waitResponse('[redo]', cmd_sender)
                        if response[0]:
                            self.broadcast('<yes>', _to=cmd_sender)
                            self.broadcast('<redo>', _from=cmd_sender)
                            self.BOARD.redo()
                        else:
                            self.broadcast('<deny>', _to=cmd_sender)
                            self.broadcast(f'[-] {response[1]} refused to redo')
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)

                case ['setpos', listMove]:
                    response = waitResponse(f'[setpos {listMove}]', cmd_sender)
                    if response[0]:
                        self.broadcast('<yes>', _to=cmd_sender)
                        self.GAME_OPENING = False
                        self.BOARD.setPosition(listMove)
                        self.broadcast(f'<setpos {listMove}>', _from=cmd_sender)
                    else:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast(f'[-] {response[1]} refused to set position')
                
                # set/detach players
                
                case ['setplayer_1']:
                    if checkPermission(command[1]) or self.player_1 is not None:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast('[SERVER] Permission denied', _to=cmd_sender)
                        continue
                    self.broadcast('<yes>', _to=cmd_sender)

                    self.player_1 = cmd_sender
                    self.__clientPermission[cmd_sender] = 1
                    self.checkGameState()
                    if self.GAME_STATE: broadcastTurn()
                    self.broadcast(f'<setplayer_1 {cmd_sender}>', _from=cmd_sender)
                
                case ['setplayer_2']:
                    if checkPermission(command[1]) or self.player_2 is not None:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast('[SERVER] Permission denied', _to=cmd_sender)
                        continue
                    self.broadcast('<yes>', _to=cmd_sender)

                    self.player_2 = cmd_sender
                    self.__clientPermission[cmd_sender] = 1
                    self.checkGameState()
                    if self.GAME_STATE: broadcastTurn()
                    self.broadcast(f'<setplayer_2 {cmd_sender}>', _from=cmd_sender)
                
                case ['detach_player_1']:
                    if self.player_1 != cmd_sender:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast('[SERVER] Permission denied', _to=cmd_sender)
                        continue
                    self.broadcast('<yes>', _to=cmd_sender)

                    self.player_1 = None
                    self.__clientPermission[cmd_sender] = 0
                    self.checkGameState()
                    self.broadcast('<detach_player_1>', _from=cmd_sender)
                
                case ['detach_player_2']:
                    if self.player_2 != cmd_sender:
                        self.broadcast('<deny>', _to=cmd_sender)
                        self.broadcast('[SERVER] Permission denied', _to=cmd_sender)
                        continue
                    self.broadcast('<yes>', _to=cmd_sender)

                    self.player_2 = None
                    self.__clientPermission[cmd_sender] = 0
                    self.checkGameState()
                    self.broadcast('<detach_player_2>', _from=cmd_sender)

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
            try:
                client, address = self.SOCKET.accept()
                client.send('[SERVER] Welcome'.encode())
                Thread(target=self.handleClientConnection, args=(client,), daemon=True).start()
            except Exception as e:
                print(f'[Error "acceptClientConnection"] {e}')


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
        def coordStr2NumStr(coord: str):
            # return f'{ord(coord[0]) - 97},{15 - int(coord[1:])}'
            return f'{ord(coord[0]) - 97},{int(coord[1:]) - 1}'

        def validString(_x, _y, *arg):
            """
            param n: Length of Board
            """
            for coord in arg:
                try:
                    # if ord(coord[0]) - 96 < 0 or ord(coord[0]) - 96 > y or int(coord[1:]) < 0 or int(coord[1:]) > y:
                    if ord(coord[0]) - 96 < 0 or \
                            ord(coord[0]) - 96 > _x or \
                            int(coord[1:]) < 0 or \
                            int(coord[1:]) > _y:
                        return False
                except:
                    return False
            return True

        def formatString(string, _x, _y):
            listMove = []
            stringCoord = ''
            while string:
                cur = string[0]
                string = string[1:]
                while len(string) > 0 and string[0].isnumeric():
                    cur += string[0]
                    string = string[1:]
                if validString(_x, _y, cur):
                    listMove.append(coordStr2NumStr(cur))
                    stringCoord += cur
            return listMove

        def getString(string, _x, _y):
            while string:
                if not validString(_x, _y, string[:2]):
                    string = string[1:]
                else:
                    string = formatString(string, _x, _y)
                    break
            return string

        position = getString(pos, self.w, self.h)
        self.clear()
        for move in position:
            self.addMove(move)

    def getPosition(self):
        return getPositionFromList(self.__listCoord)

    def getBoardSize(self):
        return self.w, self.h

    def getRecordLen(self):
        return len(self.__listCoord)

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
