from customtkinter import *
import customtkinter
from queue import Queue
import socket
from threading import Thread
import re


customtkinter.set_default_color_theme('theme.json')


def roundNum(number, places=0):
    place = 10 ** places
    rounded = (int(number * place + 0.5 if number >= 0 else -0.5)) / place
    if rounded == int(rounded):
        rounded = int(rounded)
    return rounded


class WaitWindow(CTkToplevel):
    def __init__(self):
        self.__singleton = Singleton()
        super().__init__(self.__singleton.mainWindow)
        self.title('GomokuConnection')
        self.grab_set()
        self.overrideredirect(True)
        self.label = CTkLabel(self, text='Wait server to process...')
        self.label.grid(column=0, row=0, padx=5, pady=5, sticky='we')

    def stop(self):
        self.destroy()


class Dialog(CTkToplevel):
    def __init__(self, root):
        super().__init__(root)
        self.title('GomokuConnection')
        self.grab_set()
        self.output = ...

    def show(self):
        self.setAttr()
        self.wait_window()
        return self.output

    def setAttr(self):
        pass

    def getInfo(self):
        pass

    def onClick(self):
        self.getInfo()
        if self.output is not Ellipsis:
            self.destroy()


class NameDialog(Dialog):
    def setAttr(self):
        self.__setattr__('label', CTkLabel(self, text='Name:'))
        self.__setattr__('entry', CTkEntry(self, placeholder_text='Type your nick name...'))
        self.__setattr__('button', CTkButton(self, text='Enter', text_color='#000000', width=40))

        self.label.grid(column=0, row=0, padx=5, pady=5, sticky='w')
        self.entry.grid(column=1, row=0, padx=5, pady=5, sticky='we')
        self.button.grid(column=1, row=1, padx=5, pady=5, sticky='e')

        self.entry.bind('<Return>', lambda e: self.onClick())
        self.button.configure(command=self.onClick)

    def getInfo(self):
        self.output = self.entry.get()


# noinspection PyMethodOverriding
class YesNoDialog(Dialog):
    def show(self, question):
        self.setAttr(question)
        self.wait_window()
        return self.output

    def setAttr(self, question):
        self.__setattr__('label', CTkLabel(self, text=question))
        self.__setattr__('buttonYes', CTkButton(self, text='Yes', text_color='#000000'))
        self.__setattr__('buttonNo', CTkButton(self, text='No', text_color='#000000'))

        self.label.grid(column=0, row=0, columnspan=4, padx=5, pady=5, sticky='we')
        self.buttonYes.grid(column=1, row=1, padx=5, pady=5, sticky='e')
        self.buttonNo.grid(column=2, row=1, padx=5, pady=5, sticky='e')

        self.buttonYes.configure(command=lambda: self.onClick('yes'))
        self.buttonNo.configure(command=lambda: self.onClick('no'))

    def onClick(self, answer):
        self.output = answer
        if self.output is not Ellipsis:
            self.destroy()


class Notify(CTkToplevel):
    def __init__(self, root):
        super().__init__(root)
        self.geometry()
        self.grab_set()

        self.button = CTkButton(self, text='Ok', command=self.destroy, width=80, text_color='#000000')
        self.button.grid(column=1, row=1, padx=5, pady=5, sticky='we')

        self.bind('<Return>', lambda e: self.destroy())

    def show(self, text):
        self.__setattr__('label', CTkLabel(self, text=text.center(50)))
        self.label.grid(column=0, row=0, columnspan=3, padx=5, pady=(5, 0), sticky='we')
            

class Singleton(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Singleton, cls).__new__(cls)
        return cls.instance


class Move:
    def __init__(self, coord: tuple[int, int], obj=None):
        self.coord = coord
        self.obj = obj

    def setObj(self, obj):
        self.obj = obj

    def __eq__(self, other):
        return self.coord == other.coord

    def __str__(self):
        return f'{self.coord[0]}, {self.coord[1]}'


class ClientViewModel:
    def __init__(self):
        self.__singleton = Singleton()

    def connect(self, host, port):
        try:
            self.__singleton.client.connect(host, int(port))
            # Ask Name
            name = NameDialog(self.__singleton.mainWindow).show()
            self.__singleton.client.send(name)
            self.__singleton.name = name
            self.__singleton.clientState = 1
            # Set State
            self.__singleton.board.clear()
            self.__singleton.enableAllFrame()
            # Get message from Server
        except Exception as e:
            print('[Error]:', e)
            Notify(self.__singleton.mainWindow).show(f'[Error]: {e}')


class BoardViewModel:
    def __init__(self):
        self.__singleton = Singleton()

    def setBoard(self, x, y):
        if x.isnumeric() and y.isnumeric():
            # To Client
            self.__singleton.client.send(f'<#setboard {x} {y}>')
            # Receive from Client
            # To Board
            if self.__singleton.client.getAnswer():
                self.__singleton.board.setBoardXY(int(x), int(y))

    def setPosition(self, pos, x, y):
        def coordStr2Num(coord: str):
            # return f'{ord(coord[0]) - 97},{15 - int(coord[1:])}'
            return ord(coord[0]) - 97, int(coord[1:]) - 1

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
                    listMove.append(coordStr2Num(cur))
                    stringCoord += cur
            return listMove, stringCoord

        def getString(string, _x, _y):
            while string:
                if not validString(_x, _y, string[:2]):
                    string = string[1:]
                else:
                    string = formatString(string, _x, _y)
                    break
            return string

        # To Client
        position = getString(pos, x, y)
        # self.__singleton.client.send(f'<#setpos {position[1]}>')
        print(f'<#setpos {position[1]}>')

        # Receive from Client

        # To Board
        self.__singleton.board.clear()
        for move in position[0]:
            self.__singleton.board.addMove(move[0], move[1])

    def addMove(self, move):
        if self.__singleton.clientState:
            # To Client
            self.__singleton.client.send(f'<#add {move}>')
            # Receive and To Board
            return self.__singleton.client.getAnswer()
        else:
            return False

    def clear(self, setAtt=True):
        # To Client
        if setAtt:
            self.__singleton.client.send('<#clear>')
        # Receive from Client
        # To Board
        if self.__singleton.client.getAnswer():
            self.__singleton.board.clear()

    def undo(self, setAtt=True):
        # To Client
        if setAtt:
            self.__singleton.client.send('<#undo>')
        # Receive from Client
        # To Board
        if self.__singleton.client.getAnswer():
            self.__singleton.board.undo()

    def redo(self, setAtt=True):
        # To Client
        if setAtt:
            self.__singleton.client.send('<#redo>')
        # Receive from Client
        ...
        # To Board
        if self.__singleton.client.getAnswer():
            self.__singleton.board.redo()


class PlayerViewModel:
    def __init__(self):
        self.__singleton = Singleton()

    def takeSeat1(self, name, setAtt=True):
        if not self.__singleton.clientState:
            return
        if setAtt:
            self.__singleton.client.send('<#setplayer_1>')
            if self.__singleton.client.getAnswer():
                self.__singleton.player1Name = name
                name = name[:12] + '...' if len(name) > 12 else name
                self.__singleton.player1Obj = self.__singleton.canvas1.create_text(40, 20, text=name,
                                                                                   font=('Times New Roman', 14, 'bold'),
                                                                                   fill="black", anchor='w')
        else:
            self.__singleton.player1Name = name
            name = name[:12] + '...' if len(name) > 12 else name
            self.__singleton.player1Obj = self.__singleton.canvas1.create_text(40, 20, text=name,
                                                                               font=('Times New Roman', 14, 'bold'),
                                                                               fill="black", anchor='w')

    def takeSeat2(self, name, setAtt=True):
        if not self.__singleton.clientState:
            return
        if setAtt:
            self.__singleton.client.send('<#setplayer_2>')
            if self.__singleton.client.getAnswer():
                self.__singleton.player2Name = name
                name = name[:12] + '...' if len(name) > 12 else name
                self.__singleton.player2Obj = self.__singleton.canvas2.create_text(40, 20, text=name,
                                                                                   font=('Times New Roman', 14, 'bold'),
                                                                                   fill="black", anchor='w')
        else:
            self.__singleton.player2Name = name
            name = name[:12] + '...' if len(name) > 12 else name
            self.__singleton.player2Obj = self.__singleton.canvas2.create_text(40, 20, text=name,
                                                                               font=('Times New Roman', 14, 'bold'),
                                                                               fill="black", anchor='w')

    def detachPlayer1(self, setAtt=True):
        if setAtt:
            self.__singleton.client.send('<#detach_player_1>')
            if self.__singleton.client.getAnswer():
                self.__singleton.canvas1.delete(self.__singleton.player1Obj)
                self.__singleton.player1Obj = ''
                self.__singleton.player1Name = ''
        else:
            self.__singleton.canvas1.delete(self.__singleton.player1Obj)
            self.__singleton.player1Obj = ''
            self.__singleton.player1Name = ''

    def detachPlayer2(self, setAtt=True):
        if setAtt:
            self.__singleton.client.send('<#detach_player_1>')
            if self.__singleton.client.getAnswer():
                self.__singleton.canvas2.delete(self.__singleton.player2Obj)
                self.__singleton.player2Obj = ''
                self.__singleton.player2Name = ''
        else:
            self.__singleton.canvas2.delete(self.__singleton.player2Obj)
            self.__singleton.player2Obj = ''
            self.__singleton.player2Name = ''


class ChatViewModel:
    def __init__(self):
        self.__singleton = Singleton()

    def sendMessage(self, message):
        # To ChatBox
        self.__singleton.sendText(f'{self.__singleton.name}: {message}')
        print(f'{self.__singleton.name}: {message}')
        # To Client
        self.__singleton.client.send(message)
        ...


class Board(CTkFrame):
    def __init__(self, root):
        super().__init__(root)

        self.__singleton = Singleton()

        # Setup Board Size
        self.x = 15
        self.y = 15

        # Setup Size
        self.HEIGHT = 700                 # Height is constant, also size of board
        self.__boardHSize = roundNum(self.HEIGHT * 0.88)
        self.__boardGap = roundNum(self.HEIGHT * 0.12 / 2)

        self.__distance = self.__boardHSize / (self.y - 1)

        self.__boardWSize = roundNum(self.__distance * (self.x - 1))
        self.WIDTH = self.__boardWSize + 2 * self.__boardGap

        self.__radius = roundNum(self.__distance * 0.5 * 0.90)
        self.__canvas = CTkCanvas(self, width=self.WIDTH, height=self.HEIGHT,
                                  bg='#9a9a9a', highlightthickness=0)
        self.__canvas.grid(column=0, row=0, sticky='news')

        # Bind action
        self.__canvas.bind('<Motion>', self.__realtime)
        self.__canvas.bind('<Button-1>', self.__mouseClick)
        self.__rectHover = None

        # Coordinates
        self.__coordinates = ''
        self.__realTimeCoord = self.__canvas.create_text(self.__boardGap,
                                                         self.__boardGap * 0.5,
                                                         text=self.__coordinates,
                                                         font=f"Helvetica {int(self.__boardGap * 0.25)} bold",
                                                         fill="black")
        self.__history = []
        self.__redoHistory = []
        self.__lastMove = ''

        # Color
        self.__blackColor = '#000000'
        self.__whiteColor = '#ffffff'
        self.__lastMoveColor = '#ff0000'

        # Singleton Object
        self.singleton = Singleton()
        self.singleton.toClient = Queue()

        # Finish
        self.__drawBoard()

    def __drawBoard(self):
        self.__canvas.create_rectangle(self.__boardGap, self.__boardGap,
                                       self.__boardWSize + self.__boardGap,
                                       self.__boardHSize + self.__boardGap, width=2)

        self.__canvas.create_rectangle(self.__boardGap - self.__boardGap*0.14,
                                       self.__boardGap - self.__boardGap*0.14,
                                       self.__boardWSize + self.__boardGap + self.__boardGap*0.14,
                                       self.__boardHSize + self.__boardGap + self.__boardGap*0.14, width=2)

        for i in range(self.y):
            self.__canvas.create_line(self.__boardGap, self.__boardGap + i * self.__distance,
                                      self.__boardWSize + self.__boardGap, self.__boardGap + i * self.__distance)
            self.__canvas.create_text(self.__boardWSize + self.__boardGap * 1.5 + 5,
                                      self.__boardGap + i * self.__distance,
                                      text=f'{self.y - i}', font=f"Helvetica {int(self.__boardGap * 0.25)} bold",
                                      fill="black")

        for i in range(self.x):
            self.__canvas.create_line(self.__boardGap + i * self.__distance, self.__boardGap,
                                      self.__boardGap + i * self.__distance, self.__boardHSize + self.__boardGap)
            self.__canvas.create_text(self.__boardGap + i * self.__distance,
                                      self.__boardHSize + self.__boardGap * 1.5 + 5,
                                      text=chr(65 + i), font=f"Helvetica {int(self.__boardGap * 0.25)} bold",
                                      fill="black")

    def __drawCircle(self, x, y, color=0):
        color = self.__blackColor if color == 0 else self.__whiteColor
        move = self.__canvas.create_oval(x - self.__radius, y - self.__radius,
                                         x + self.__radius, y + self.__radius, fill=color)
        self.__setLastMove(x, y)
        return move

    def __valid(self, x, y):
        return 0 <= x - self.__boardGap <= self.__boardWSize and 0 <= y - self.__boardGap <= self.__boardHSize

    def __realtime(self, event):
        def hoverSquare():
            return self.__canvas.create_rectangle(x1 - self.__radius, y1 - self.__radius,
                                                  x1 + self.__radius, y1 + self.__radius, fill='', )

        x, y = event.x, event.y
        x1 = self.__boardGap + roundNum(roundNum((x - self.__boardGap) / self.__distance) * self.__distance)
        y1 = self.__boardGap + roundNum(roundNum((y - self.__boardGap) / self.__distance) * self.__distance)
        if self.__valid(x, y):
            self.__canvas.delete(self.__realTimeCoord)
            self.__canvas.delete(self.__rectHover)
            self.__coordinates = f'{chr(97 + roundNum((x - self.__boardGap) / self.__distance))}' \
                                 f'{self.y - roundNum((y - self.__boardGap) / self.__distance)}'
            self.__realTimeCoord = self.__canvas.create_text(self.__boardGap,
                                                             self.__boardGap * 0.5,
                                                             text=self.__coordinates,
                                                             font=f"Helvetica {int(self.__boardGap * 0.25)} bold",
                                                             fill="black")
            self.__rectHover = hoverSquare()
        else:
            self.__canvas.delete(self.__realTimeCoord)
            self.__canvas.delete(self.__rectHover)

    def __mouseClick(self, event):
        # To Board
        x, y = event.x, event.y
        x1 = self.__boardGap + roundNum(roundNum((x - self.__boardGap) / self.__distance) * self.__distance)
        y1 = self.__boardGap + roundNum(roundNum((y - self.__boardGap) / self.__distance) * self.__distance)
        # To client
        if self.__singleton.boardViewModel.addMove(self.convertCoordToInt(x, y)):
            self.__makeMove(x1, y1)

    def __setLastMove(self, x, y):
        self.__canvas.delete(self.__lastMove)
        self.__lastMove = self.__canvas.create_oval(x - self.__radius * 0.2, y - self.__radius * 0.2,
                                                    x + self.__radius * 0.2, y + self.__radius * 0.2,
                                                    fill=self.__lastMoveColor)

    def __makeMove(self, x, y):
        move = Move((x, y))
        if self.__valid(x, y) and move not in self.__history:
            move.setObj(self.__drawCircle(x, y, len(self.__history) % 2))
            if self.__redoHistory and move != self.__redoHistory[-1]:
                self.__redoHistory.clear()
            elif self.__redoHistory and move == self.__redoHistory[-1]:
                self.__redoHistory.pop()
            self.__history.append(move)

    def setBoardXY(self, x, y):
        self.x = x
        self.y = y

        self.clear()
        self.__canvas.delete('all')

        self.__distance = self.__boardHSize / (self.y - 1)
        self.__boardWSize = roundNum(self.__distance * (self.x - 1))
        self.WIDTH = self.__boardWSize + 2 * self.__boardGap
        self.__canvas.configure(width=self.WIDTH)

        self.__radius = roundNum(self.__distance * 0.5 * 0.90)

        self.__drawBoard()

    def undo(self):
        if self.__history:
            move = self.__history.pop()
            self.__redoHistory.append(move)
            self.__canvas.delete(move.obj)
            if self.__history:
                self.__setLastMove(*self.__history[-1].coord)
            else:
                self.__canvas.delete(self.__lastMove)
                self.__lastMove = ''

    def redo(self):
        if self.__redoHistory:
            move = self.__redoHistory.pop()
            move.setObj(self.__drawCircle(move.coord[0], move.coord[1], len(self.__history) % 2))
            self.__history.append(move)
            self.__setLastMove(*self.__history[-1].coord)

    def clear(self):
        self.__redoHistory.clear()
        for move in self.__history:
            self.__canvas.delete(move.obj)
        self.__history.clear()
        self.__canvas.delete(self.__lastMove)
        self.__lastMove = ''

    def addMove(self, x, y):
        self.__makeMove(*self.convertIntToCoord(x, y))

    def convertCoordToString(self, x, y):
        return f'{chr(97 + roundNum((x - self.__boardGap) / self.__distance))}' \
               f'{self.y - roundNum((y - self.__boardGap) / self.__distance)}'

    def convertIntToCoord(self, x, y):
        x = x * self.__distance + self.__boardGap
        y = (self.y - y - 1) * self.__distance + self.__boardGap
        return x, y

    def convertCoordToInt(self, x, y):
        return f'{roundNum((x - self.__boardGap) / self.__distance)},' \
               f'{self.y - roundNum((y - self.__boardGap) / self.__distance) - 1}'


class ClientFrame(CTkFrame):
    def __init__(self, root):
        super().__init__(root)
        self.grid_columnconfigure(1, weight=1)

        self.__viewModel = ClientViewModel()

        self.label0 = CTkLabel(self, text='Host:')
        self.label0.grid(column=0, row=0, padx=5, pady=(5, 0), sticky='w')
        self.label1 = CTkLabel(self, text='Port:')
        self.label1.grid(column=0, row=1, padx=5, pady=(5, 0), sticky='w')

        self.entryHost = CTkEntry(self)
        self.entryHost.grid(column=1, row=0, padx=5, pady=(5, 0), sticky='we')
        self.entryPort = CTkEntry(self)
        self.entryPort.grid(column=1, row=1, padx=5, pady=(5, 0), sticky='we')

        self.connectButton = CTkButton(self, text='Connect', fg_color='#c7c7c7', text_color='#000000')
        self.connectButton.grid(column=1, row=2, padx=5, pady=5, sticky='e')
        self.connectButton.configure(command=lambda: self.__viewModel.connect(self.entryHost.get(),
                                                                              self.entryPort.get()))


class ChatFrame(CTkFrame):
    def __init__(self, root):
        super().__init__(root)
        self.__singleton = Singleton()
        self.__viewModel = ChatViewModel()

        self.grid_columnconfigure(1, weight=1)
        # TextBox
        self.textBox = CTkTextbox(self, height=150, width=450, state='disabled')
        self.textBox.grid(row=0, column=0, columnspan=40, padx=5, pady=5, sticky='we')
        # Label
        self.label = CTkLabel(self, text='Message:')
        self.label.grid(column=0, row=1, padx=5, pady=5, sticky='w')
        # Entry
        self.entry = CTkEntry(self, placeholder_text='message...')
        self.entry.grid(column=1, row=1, padx=5, pady=5, sticky='we')
        # Button
        self.button = CTkButton(self, text='Send', fg_color='#c7c7c7', text_color='#000000', width=80)
        self.button.grid(column=39, row=1, padx=5, pady=5, sticky='we')

        self.__singleton.sendText = self.sendText

        self.button.configure(command=lambda: self.__viewModel.sendMessage(self.entry.get()))
        self.entry.bind('<Return>', command=lambda e: self.__viewModel.sendMessage(self.entry.get()))

    def sendText(self, message):
        self.entry.delete(0, 'end')

        self.textBox.configure(state='normal')
        self.textBox.insert('end', f'{message}\n')
        self.textBox.configure(state='disabled')
        self.textBox.see('end')

    def clearText(self):
        self.textBox.delete('0.0', 'end')


class SettingFrame(CTkFrame):
    def __init__(self, root):
        super().__init__(root)

        self.singleton = Singleton()
        self.__viewModel = BoardViewModel()
        self.__playerViewModel = PlayerViewModel()

        self.singleton.boardViewModel = self.__viewModel
        self.singleton.playerViewModel = self.__playerViewModel

        self.frame = CTkFrame(self)
        self.frame.grid(column=0, row=1, padx=5, pady=(5, 0), sticky='news')

        self.frame1 = CTkFrame(self)
        self.frame1.grid(column=0, row=2, padx=5, pady=5, sticky='news')

        self.frame2 = CTkFrame(self)
        self.frame2.grid(column=0, row=0, padx=5, pady=(5, 0), sticky='news')

        # Group 1
        self.labelBoardSize = CTkLabel(self.frame, text='Board:')
        self.labelBoardSize.grid(column=0, row=0, padx=5, pady=5, sticky='w')
        self.label0 = CTkLabel(self.frame, text='x')
        self.label0.grid(column=2, row=0, padx=5, pady=5, sticky='we')
        self.labelPos = CTkLabel(self.frame, text='Position:')
        self.labelPos.grid(column=0, row=1, padx=5, pady=5, sticky='w')

        self.entryX = CTkEntry(self.frame, width=30, justify='center')
        self.entryX.grid(column=1, row=0, padx=5, sticky='we')
        self.entryY = CTkEntry(self.frame, width=30, justify='center')
        self.entryY.grid(column=3, row=0, padx=5, sticky='we')
        self.entryPos = CTkEntry(self.frame, width=290)
        self.entryPos.grid(column=1, row=1, columnspan=3, padx=5, sticky='we')

        self.setBoard = CTkButton(self.frame, text='Set', fg_color='#c7c7c7', text_color='#000000', width=80)
        self.setBoard.grid(column=4, row=0, padx=5, sticky='we')
        self.setPos = CTkButton(self.frame, text='Set', fg_color='#c7c7c7', text_color='#000000', width=80)
        self.setPos.grid(column=4, row=1, padx=5, sticky='we')

        self.setBoard.configure(command=lambda: self.__viewModel.setBoard(self.entryX.get(), self.entryY.get()))
        self.setPos.configure(command=lambda: self.__viewModel.setPosition(self.entryPos.get().strip(),
                                                                           self.singleton.board.x,
                                                                           self.singleton.board.y))
        self.entryPos.bind('<Return>', command=lambda e: self.__viewModel.setPosition(self.entryPos.get().strip(),
                                                                                      self.singleton.board.x,
                                                                                      self.singleton.board.y))

        # Group 2
        self.undoButton = CTkButton(self.frame1, text='Undo', fg_color='#c7c7c7', text_color='#000000')
        self.undoButton.grid(column=0, row=2, padx=5, pady=5, sticky='we')
        self.redoButton = CTkButton(self.frame1, text='Redo', fg_color='#c7c7c7', text_color='#000000')
        self.redoButton.grid(column=1, row=2, padx=5, pady=5, sticky='we')
        self.clearButton = CTkButton(self.frame1, text='Clear', fg_color='#c7c7c7', text_color='#000000')
        self.clearButton.grid(column=3, row=2, padx=5, pady=5, sticky='we')

        self.clearButton.configure(command=self.__viewModel.clear)
        self.undoButton.configure(command=self.__viewModel.undo)
        self.redoButton.configure(command=self.__viewModel.redo)

        # Group 3
        self.canvas = CTkCanvas(self.frame2, width=200, height=40, bg='#ffffff', highlightthickness=0)
        self.canvas.grid(column=0, row=0, padx=5, pady=5, sticky='we')

        self.canvas1 = CTkCanvas(self.frame2, width=200, height=40, bg='#ffffff', highlightthickness=0)
        self.canvas1.grid(column=1, row=0, padx=5, pady=5, sticky='we')

        self.seat1Button = CTkButton(self.canvas, text='X', font=('Times New Roman', 14, 'bold'), width=20, height=20,
                                     fg_color='#413e41', hover_color='#cccccc')
        self.seat1Button.place(x=170, y=10)

        self.seat2Button = CTkButton(self.canvas1, text='X', font=('Times New Roman', 14, 'bold'), width=20, height=20,
                                     fg_color='#413e41', hover_color='#cccccc')
        self.seat2Button.place(x=170, y=10)

        # Decorate
        self.canvas.create_rectangle(0, 0, 20, 40, fill='#000000')
        self.canvas.create_text(12, 20, text='1', font=('Times New Roman', 14, 'bold'),
                                fill="#ffffff")

        self.canvas1.create_rectangle(0, 0, 20, 40, fill='#000000')
        self.canvas1.create_text(12, 20, text='2', font=('Times New Roman', 14, 'bold'),
                                 fill="#ffffff")

        self.canvas.bind('<Button-1>', lambda e: self.__playerViewModel.takeSeat1(self.singleton.name))
        self.canvas1.bind('<Button-1>', lambda e: self.__playerViewModel.takeSeat2(self.singleton.name))

        self.singleton.player1Obj = ''
        self.singleton.player2Obj = ''
        self.singleton.canvas1 = self.canvas
        self.singleton.canvas2 = self.canvas1


class Client:
    def __init__(self):
        self.__host = ''
        self.__port = 0
        self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.STATE = 1

        self.singleton = Singleton()
        self.singleton.player1Name = ''
        self.singleton.player2Name = ''

        self.decideQueue = Queue()

    def connect(self, host, port):
        self.__host = host
        self.__port = port
        self.SOCKET.connect((self.__host, self.__port))
        Thread(target=self.receive, daemon=True).start()

    def receive(self):
        while self.STATE:
            message = self.SOCKET.recv(1024).decode().strip()
            if re.match('^<(.*?)>$', message):
                print('--> Command:', message)
                command = re.match("^<(.*?)>$", message).group(1)
                print('Command After Re:', command)
                self.handleServerCommand(command)
            else:
                print('Message:', message)
                self.singleton.sendText(message)

    def send(self, message):
        self.SOCKET.send(message.encode())

    def handleServerCommand(self, command: str):
        print('command:', command)
        print('command SP:', command.split())
        print()
        match command.split():
            case ['setboard', x, y]:
                self.singleton.board.setBoardXY(int(x), int(y))
            case ['setplayer_1', name]:
                self.singleton.playerViewModel.takeSeat1(name, False)
            case ['setplayer_2', name]:
                self.singleton.playerViewModel.takeSeat2(name, False)
            case ['detach_player_1']:
                self.singleton.playerViewModel.detachPlayer1(False)
            case ['detach_player_2']:
                self.singleton.playerViewModel.detachPlayer2(False)
            case ['yes']:
                self.decideQueue.put(True)
            case ['deny' | 'no']:
                self.decideQueue.put(False)
            case ['ask', *question]:
                answer = YesNoDialog(self.singleton.mainWindow).show(' '.join(question))
                if answer:
                    self.send('<#yes>')
                else:
                    self.send('<#no>')
            case ['add', move]:
                x, y = move.split(',')
                self.singleton.board.addMove(int(x), int(y))
            case ['undo']:
                self.singleton.board.undo()
            case ['redo']:
                self.singleton.board.redo()
            case ['clear']:
                self.singleton.board.clear()

    def getAnswer(self):
        waitWindow = WaitWindow()
        while self.decideQueue.empty():
            continue
        waitWindow.destroy()
        return self.decideQueue.get()

    def interact(self):
        name = input('Type your name: ')
        self.send(name)
        Thread(target=self.receive, daemon=True).start()
        while self.STATE:
            # getInput = input('Message: ')
            # self.send(getInput)
            ...


class ViewModel:
    def __init__(self):
        self.__singleton = Singleton()


class View(CTk):
    def __init__(self):
        super().__init__()

        self.title('GomokuConnection')
        self.resizable(False, False)

        self.__viewModel = ViewModel()
        self.__singleton = Singleton()

        self.board = Board(self)
        self.chatFrame = ChatFrame(self)
        self.settingFrame = SettingFrame(self)
        self.clientFrame = ClientFrame(self)

        self.board.grid(column=0, row=0, rowspan=50, sticky='new')
        self.settingFrame.grid(column=1, row=0, padx=5, pady=(5, 0), sticky='news')
        self.clientFrame.grid(column=1, row=1, padx=5, pady=(5, 0), sticky='news')
        self.chatFrame.grid(column=1, row=49, padx=5, pady=5, sticky='news')

        self.setStateFrame(self.settingFrame, 'disabled')
        self.setStateFrame(self.chatFrame, 'disabled')

        self.__singleton.board = self.board
        self.__singleton.mainWindow = self
        self.__singleton.client = Client()
        self.__singleton.boardToClient = Queue()
        self.__singleton.viewModel = self.__viewModel
        self.__singleton.setStateFrame = self.setStateFrame
        self.__singleton.enableAllFrame = self.__enableAllFrame
        self.__singleton.name = ''
        self.__singleton.clientState = 0

    def setStateFrame(self, frame: CTkFrame, option):
        for widget in frame.winfo_children():
            if isinstance(widget, CTkFrame):
                self.setStateFrame(widget, option)
            else:
                try:
                    widget.configure(state=option)
                except:
                    continue

    def __enableAllFrame(self):
        self.setStateFrame(self.settingFrame, 'normal')
        self.setStateFrame(self.chatFrame, 'normal')


def main():
    view = View()
    view.mainloop()


if __name__ == '__main__':
    main()
