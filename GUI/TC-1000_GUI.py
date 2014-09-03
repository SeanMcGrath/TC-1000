"""
TO DO: Celsius/Fahrenheit communication
"""

"""
This recipe depends on PyQt and pySerial. Qt 4 is world class code 
and I like how it looks. PyQt is not completely open source, 
but I think PySide is. Tested on Qt4.6 / Win 7 / Duemilanove

Author: Dirk Swart, Ithaca, NY. 2011-05-20. www.wickeddevice.com

Based on threads recipe by Jacob Hallen, AB Strakt, Sweden. 2001-10-17
As adapted by Boudewijn Rempt, Netherlands. 2002-04-15

PS: This code is provided with no warranty, express or implied. It is 
meant to demonstrate a concept only, not for actual use. 
Code is in the public domain.
"""
__author__ = 'Dirk Swart, Doudewijn Rempt, Jacob Hallen'

import sys, time, math, threading, random, queue, glob, matplotlib as mpl, numpy as np
from PyQt5 import QtGui, QtCore, QtWidgets
from datetime import datetime
import serial

def serial_ports():
    """Lists serial ports

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
    if sys.platform.startswith('win'):
        ports = ['COM' + str(i + 1) for i in range(1,256)] #exclude COM1

    elif sys.platform.startswith('linux'):
        # this is to exclude your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')

    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')

    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def toFahrenheit(celsius):
    return (float(celsius)*9.0/5.0)+32.0

def toCelsius(fahrenheit):
    return (float(fahrenheit)-32.0)*(5.0/9.0)

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, monitor, endcommand, stylesheet, *args):

        QtWidgets.QMainWindow.__init__(self, *args)

        self.monitor = monitor
        self.setCentralWidget(monitor)

        self.initUI()

        self.endcommand = endcommand

        self.setStyleSheet(stylesheet.read())

    def initUI(self):
        exitAction = QtWidgets.QAction(QtGui.QIcon('exit.png'), '&Exit', self)        
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.closeEvent)

        self.setWindowTitle('TC-1000 Readout')
        self.statusBar().showMessage("Ready")

        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(exitAction)

    def closeEvent(self, ev):
        self.endcommand()


class SerialMonitor(QtWidgets.QWidget):

    def __init__(self, queue, endcommand, ports, *args):

        # Celsius default
        self.fahrenheit = 0

        # internal temperature trackers in celsius
        self.current = 27
        self.target = 30

        #superclass constructor
        QtWidgets.QWidget.__init__(self, *args)

        #take queue from constructor
        self.queue = queue

        # Create array for temperature storage
        self.tempArray = []

        # declare subwidgets
        self.portSelector = QtWidgets.QComboBox(self)
        for port in ports:
            self.portSelector.addItem(port)
        self.portLabel = QtWidgets.QLabel(self)
        if(ports):
            self.portLabel.setText("Serial Port")
        else:
            self.portLabel.setText("NO PORTS")
        self.fSelect = QtWidgets.QRadioButton("Fahrenheit",self)
        self.cSelect = QtWidgets.QRadioButton("Celsius",self)
        self.cSelect.setChecked(True)
        self.currLabel = QtWidgets.QLabel(self)
        self.currLabel.setText("Current Temperature")
        self.targetLabel = QtWidgets.QLabel(self)
        self.targetLabel.setText("Target Temperature")
        self.currTemp = QtWidgets.QLCDNumber(6,self)
        self.targetTemp = QtWidgets.QSpinBox(self)
        self.targetTemp.setMaximum(1000)

        # Create widget layout
        self.grid = QtWidgets.QGridLayout()
        self.grid.addWidget(self.portLabel,1,1)
        self.grid.addWidget(self.portSelector,2,1)
        self.grid.addWidget(self.cSelect,1,2)
        self.grid.addWidget(self.fSelect,2,2)
        self.grid.addWidget(self.currLabel,3,1)
        self.grid.addWidget(self.targetLabel,3,2)
        self.grid.addWidget(self.currTemp,4,1)
        self.grid.addWidget(self.targetTemp,4,2)
        self.grid.rowStretch(1)
        self.setLayout(self.grid)

        self.show()
        self.endcommand = endcommand    
        
    def closeEvent(self, ev):
        self.endcommand()

    def processIncoming(self):
        """
        Handle all the messages currently in the queue (if any).
        """
        while self.queue.qsize():
            try:
                #grab next item in queue
                msg = self.queue.get(0).decode("utf-8").split()
                #decode bytes to string and parse packet
                if len(msg) == 1:
                    self.current = float(msg[0])
                elif len(msg) == 2:
                    self.current =float(msg[0])
                    self.fahrenheit = int(msg[1])
                    if (int(self.fahrenheit)):
                        self.fSelect.setChecked(True)
                        self.targetTemp.setSuffix(" F")
                        self.targetTemp.setValue(int(toFahrenheit(float(self.target))))
                elif len(msg) == 3:
                    self.current = float(msg[0])
                    self.fahrenheit = int(msg[1])
                    self.target = float(msg[2])
                    if (int(self.fahrenheit)):
                        self.fSelect.setChecked(True)
                        self.targetTemp.setSuffix(" F")
                        self.targetTemp.setValue(int(toFahrenheit(self.target)))
                    else:
                        self.cSelect.setChecked(True)
                        self.targetTemp.setSuffix(" C")
                        self.targetTemp.setValue(int(self.target))
                
                if int(self.fahrenheit):
                    self.currTemp.display(toFahrenheit(self.current))
                else:
                    self.currTemp.display(self.current)

                self.tempArray.append({datetime.now(),self.current})
                
            except queue.Empty:
                print("queue empty")
                pass


        # print("handled all messages in queue")
            

class ThreadedClient:
    """
    Launch the main part of the GUI and the worker thread. periodicCall and
    endApplication could reside in the GUI part, but putting them here
    means that you have all the thread controls in a single place.
    """
    running = 0
    serialPort = 0
    ssFile = "SerialMonitor.stylesheet"
    ports = serial_ports()
    if(ports):
        serialPort = ports[0]

    def __init__(self):
        # Create the queues
        self.outVal = 0
        self.inQueue = queue.LifoQueue()
        self.outQueue = queue.LifoQueue()

        # load stylesheet
        self.ss = open(self.ssFile,"r")

        # Start Serial Connection
        if self.serialPort:
            self.initSerial(self.serialPort,9600)

        # Set up the GUI part
        self.monitor=SerialMonitor(self.inQueue, self.endWidget,self.ports)
        self.gui = MainWindow(self.monitor,self.endApplication,self.ss)
        self.gui.show()

        # A timer to periodically call periodicCall :-)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.periodicCall)
        # Start the timer -- this replaces the initial call to periodicCall
        self.timer.start(50)

        # Connect spinbox to target temp on Arduino
        self.monitor.targetTemp.valueChanged.connect(self.writeData)

        # Connect port selector
        self.monitor.portSelector.currentIndexChanged.connect(self.changePort)

        # connect scale selector
        self.monitor.fSelect.toggled.connect(self.scaleChange)

        # Set up the thread to do asynchronous I/O
        # More can be made if necessary
        self.running = 1
        self.thread1 = threading.Thread(target=self.workerThread1)
        self.thread1.start()

    def periodicCall(self):
        """
        Check every 10 ms if there is something new in the queue.
        """
        self.monitor.processIncoming()
        if not self.running:
            root.quit()
            print("Quit")

    def initSerial(self,port,baud):
        """
        Initialize serial connection
        """
        try:
            self.ser = serial.Serial(port, baud)
            return True
        except (OSError,serial.SerialException):
            pass

        return False

    def writeData(self, data):
        """
        write value from spinbox to output queue
        """
        if not self.monitor.fahrenheit:
            if(data > self.monitor.target):
                self.monitor.target += 1
            elif(data < self.monitor.target):
                self.monitor.target -= 1
        else:
            if(data > toFahrenheit(self.monitor.target)):
                self.monitor.target += 5.0/9.0
            elif(data < toFahrenheit(self.monitor.target)):
                self.monitor.target -= 5.0/9.0

        self.outQueue.put(self.monitor.target)

    def scaleChange(self, scale):
        """
        implement radio button control of temp scale
        """
        self.monitor.fahrenheit = scale
        self.monitor.target = math.floor(self.monitor.target)
        if(scale):
            self.outQueue.put("F")
            self.monitor.currTemp.display(toFahrenheit(self.monitor.current))
            self.monitor.targetTemp.setSuffix(" F")
            self.monitor.targetTemp.setValue(int(toFahrenheit(self.monitor.target)))
        else:
            self.monitor.currTemp.display(float(self.monitor.current))
            self.monitor.targetTemp.setValue(float(self.monitor.target))
            self.monitor.targetTemp.setSuffix(" C")
            self.outQueue.put("C")

    def endWidget(self):
        """
        Gracefully close main widget
        """
        print("Closing widget...")
        self.running = 0
        # close serial connection - exit hangs if this fails
        self.ser.close()
        print("Serial closed...")

    def endApplication(self):
        """
        Gracefully close application
        """
        print("Closing application...")
        self.monitor.close()


    def changePort(self, portIndex):
        try:
            self.ser.close()
            self.initSerial(self.ports[portIndex],9600)
            self.ser.open()
        except:
            self.monitor.portLabel.setText("Error on " + self.ports[portIndex])
            pass

    def workerThread1(self):
        """
        This is where we handle the asynchronous I/O. 
        """
        print("thread started!")
        while self.running:
            oldOut = 0;

            # If no port is available, continuously check for one
            while (not self.ports) and self.running:
                print("looking for ports")
                self.monitor.portSelector.clear()
                self.ports = serial_ports()
                # if found
                if(self.ports):
                    self.monitor.portSelector.addItem(self.ports[0])
                    self.monitor.portLabel.setText("Connecting...")
                    self.initSerial(self.ports[0],9600)
                    time.sleep(.5)

            print("there is a port")

            while self.ports and self.running:
                #Poll serial for input and enqueue it
                try:
                    msgIn = self.ser.readline();
                    if (msgIn):
                        self.monitor.portLabel.setText("Serial Port")
                        self.inQueue.put(msgIn)
                    else:
                        pass
                except serial.serialutil.SerialException:
                    try:
                        self.ser.readline()
                    except serial.serialutil.SerialException:
                        self.monitor.portLabel.setText("Error on " + self.ports[0])
                        self.monitor.currTemp.display("")
                        self.ports = []

                # push output from queue to serial
                if self.outQueue.qsize():
                    self.outVal = self.outQueue.get()
                    self.ser.write(str(self.outVal).encode("utf-8"))
                    self.ser.write('\n'.encode("utf-8"))




root = QtWidgets.QApplication(sys.argv)
client = ThreadedClient()
sys.exit(root.exec_())
