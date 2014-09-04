"""
================
TC-1000 GUI
================

Read out and control the Antares Micro TC-1000 PID controller.

Built for PyQt5 on Python 3.4.

Author: Sean McGrath, Amherst, MA, 2014. srmcgrat@umass.edu

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
    """
    Lists serial ports

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
    """
    Converts input to Fahrenheit scale.

    celsius
        Input temperature in Celsius
    """
    return (float(celsius)*9.0/5.0)+32.0

def toCelsius(fahrenheit):
    """
    Converts input to Celsius.

    fahrenheit
        input temperature in Fahrenheit
    """
    return (float(fahrenheit)-32.0)*(5.0/9.0)

class MainWindow(QtWidgets.QMainWindow):
    """
    Main GUI Window, which contains and displays subwidgets.
    """

    def __init__(self, widgets, endcommand, stylesheet, *args):
        """
        Constructor.

        widgets
            list of subwidgets to be hosted in this window

        endcommand
            a function to be called when this window receives a CloseEvent

        stylesheet
            a .stylesheet file opened in read mode contiang style information

        """

        # Superconstructor
        QtWidgets.QMainWindow.__init__(self, *args)

        # Initialize SerialMonitor
        self.monitor = widgets[0]
        self.setCentralWidget(widgets[0])

        # 
        self.initUI()

        self.endcommand = endcommand

        self.setStyleSheet(stylesheet.read())

    def initUI(self):
        """
        Assemble and initialize window UI.
        """

        # File->Exit
        exitAction = QtWidgets.QAction(QtGui.QIcon('exit.png'), '&Exit', self)        
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.closeEvent)

        # Put title on window
        self.setWindowTitle('TC-1000 Readout')

        # Initialize status bar at bottom of window
        self.statusBar().showMessage("Initializing")

        # Initialize "File" Section of top menu
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(exitAction)

    def closeEvent(self, ev):
        """
        Executed when window is closed or File->Exit is called.

        ev
            The CloseEvent in question. This is accepted by default.
        """

        self.endcommand()


class SerialMonitor(QtWidgets.QWidget):
    """
    Widget to collect and display temperature information from TC-1000.
    Also allows graphical control of on-board variables.

    This widget DOES NOT handle actual I/O - this is handled by ThreadedClient, which acquires
    data and passes it to the graphical monitor via a LifoQueue.
    """

    def __init__(self, queue, endcommand, ports, *args):
        """
        Constructor.

        queue
            the input LifoQueue passed from the client application.

        endcommand
            the body of a funtion to be called at widget termination.

        ports
            A list of available serial ports
        """

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
        self.portLabel.setText("Serial Port")
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
        """
        Executed when window is closed or File->Exit is called.

        ev
            The CloseEvent in question. This is accepted by default.
        """
        self.endcommand()

    def processIncoming(self):
        """
        Handle all the messages currently in the input queue (if any).
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

                # add the temperature to array for analysis
                self.tempArray.append({datetime.now(),self.current})
                
            except queue.Empty:
                print("queue empty")
                pass

            

class ThreadedClient:
    """
    Launches the GUI and handles I/O.

    GUI components reside within the body of the class itself, while actual serial communication
    is in a separate thread.
    """
    BAUD_RATE = 9600
    running = 0
    serialPort = 0
    ssFile = "SerialMonitor.stylesheet"
    ports = serial_ports()
    if(ports):
        serialPort = ports[0]

    def __init__(self):
        """
        Constructor.
        """

        # Create the queues
        self.outVal = 0
        self.inQueue = queue.LifoQueue()
        self.outQueue = queue.LifoQueue()

        # load stylesheet
        self.ss = open(self.ssFile,"r")

        # Start Serial Connection
        if self.serialPort:
            self.initSerial(self.serialPort,self.BAUD_RATE)

        # Set up the GUI part
        self.monitor=SerialMonitor(self.inQueue, self.endWidget,self.ports)
        self.widgets = [self.monitor]
        self.gui = MainWindow(self.widgets,self.endApplication,self.ss)
        self.gui.show()

        # A timer to periodically call periodicCall
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
        self.running = 1
        self.thread1 = threading.Thread(target=self.workerThread1)
        self.thread1.start()

    def periodicCall(self):
        """
        Check every 50 ms if there is something new in the queue.
        Also checks whether the program has closed.
        """
        self.monitor.processIncoming()
        if not self.running:
            root.quit()
            print("Quit")

    def initSerial(self,port,baud = BAUD_RATE):
        """
        Initialize serial connection.

        port
            string holding name of desired port (eg. COM4)

        baud
            integer baud rate. Defaults to BAUD_RATE bps.

        :Returns:
            True if connection was successful, False otherwise.
        """

        try:
            self.ser = serial.Serial(port, baud)
            return True
        except (OSError,serial.SerialException):
            pass

        return False

    def writeData(self, data):
        """
        Implement spinbox control of temperature variables.
        Write target temperature value from spinbox to output queue.

        data
            new value of spinbox.
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
        Implement radio button control of temperature scale.
        Write scale type to output queue.

        scale
            Boolean value: True for Fahrenheit, False for Celsius
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
        Gracefully close SerialMonitor (hopefully)
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
        """
        Take input from combobox to change serial port.

        portIndex
            index into ports list corresponding to desired port
        """
        try:
            self.ser.close()
            self.initSerial(self.ports[portIndex],BAUD_RATE)
            self.ser.open()
        except:
            self.gui.statusBar().showMessage("Error on " + self.ports[portIndex])
            pass

    def workerThread1(self):
        """
        Handles asynchronous I/O.

        Pulls raw port input in line by line and places it in a queue which is passed to the SerialMonitor widget.
        Output from SerialMonitor subwidget is placed in the output queue by various methods above,
        and each time through the loop, the most recent output is encoded and sent to the control module.
        """
        while self.running:
            # If no port is available, continuously check for one
            while (not self.ports) and self.running:
                self.gui.statusBar().showMessage("No Serial Ports Detected")
                self.monitor.portSelector.clear()
                self.ports = serial_ports()
                # if found
                if(self.ports):
                    self.gui.statusBar().showMessage("Connecting to " + self.ports[0] + "...")
                    self.monitor.portSelector.addItem(self.ports[0])
                    self.initSerial(self.ports[0],self.BAUD_RATE)
                    time.sleep(.5)

            while self.ports and self.running:
                #Poll serial for input and enqueue it
                try:
                    msgIn = self.ser.readline();
                    if (msgIn):
                        self.gui.statusBar().showMessage("Serial connection active")
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

                # push next available output from queue to serial
                if self.outQueue.qsize():
                    self.outVal = self.outQueue.get()
                    self.ser.write(str(self.outVal).encode("utf-8"))
                    self.ser.write('\n'.encode("utf-8"))




root = QtWidgets.QApplication(sys.argv)
client = ThreadedClient()
sys.exit(root.exec_())
