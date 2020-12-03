import pyvisa
import json
import re
import time
import numpy as np
import plotly.graph_objects as go

def roundSigFig(data, maxSF = 4):
    """
    { function_description }
    
    :param      data:   The data
    :type       data:   { type_description }
    :param      maxSF:  The maximum sf
    :type       maxSF:  number
    """
    floatMatches = list(re.finditer('\d+\.\d+', data))
    dataList = []
    prevEndIndex = 0
    for floatMatch in floatMatches:
        floatStartI = floatMatch.span()[0]
        floatEndI = floatMatch.span()[1]
        floatStr = data[floatStartI:floatEndI]
        ##### Find the first non zero or decimal point and truncate the float string to the correct number of sig fig.
        floatStr = f'{float(floatStr):.{maxSF}}'
        dataList.append(data[prevEndIndex:floatStartI])
        dataList.append(floatStr)
        prevEndIndex = floatEndI
    # add remaining data after last float
    lastFloatEndIndex = floatMatches[-1].span()[1]
    dataList.append(data[lastFloatEndIndex:])
    # make in to string
    return ''.join(dataList)

def getTimeStr():
    t = time.gmtime()
    return f'{t.tm_year-2000:02}{t.tm_mon:02}{t.tm_mday:02}_{t.tm_hour:02}{t.tm_min:02}{t.tm_sec:02}'

def connectKeithley(inst_ip = "192.168.0.2",inst_port = "1394",timeout=10E3):
    """
    Sets up VISA comms with a TCP/IP VISA resurce at the given ip adress and port,
    then queries the identitiy of the resource and prints any response
    
    Also starts measuring the voltage on the middle pin of the array plate (125 on the multiplexer)
    
    Keyword arguments
    timeout -- the timeout of the resource (default 10E3 ms)
    """
    rm = pyvisa.ResourceManager('@py')
    dmm = rm.open_resource('TCPIP0::'+inst_ip+'::'+inst_port+'::SOCKET')
    dmm.read_termination = '\n' #must set the termination character for the instrument 
    dmm.timeout=timeout
    print(dmm.query('*IDN?'))
    setup = [
        '*RST', # resets the device
        'TRAC:CLE', # clears the buffer
        "ROUT:OPEN:ALL", # makes sure all connections on the multiplexer are open (disconnected)
        "ROUT:CLOS (@125)", # connects the middle pin of the array plate to the meter
        "FUNC 'VOLT',(@125)", # makes sure it's a voltage reading we are taking.
        "INIT:CONT ON", # continuously sample so get updates on front panel.
        'FORM:ELEM READ',#, UNIT, TST, CHAN, LIM' #lots of spare data, for some reason?
    ]
    for cmd in setup:
        dmm.write(cmd)
#         time.sleep(.1)
    
    return dmm

def disconnectKeithley(dmm):
    dmm.close()
    return

def disconnectVisa():
    "Use this to close all open socket resources in the case that you lose the "
    pyvisa.ResourceManager('@py').close()
    return

def readMiddlePin(dmm, read = False):

    if read:
        comArray = [
            "TRAC:CLE", # Clear buffer.
            "INIT:CONT OFF", # Disable continuous initiation.
            "TRIG:SOUR IMM", # Select the immediate control source.
            "TRIG:COUN 1", # Set to perform one scan.
            "SAMP:COUN 1", # Set to scan 10 channels.
            "ROUT:SCAN (@125)", # Set scan to channel 125
            "ROUT:SCAN:TSO IMM", # Start scan when enabled and triggered.
            "ROUT:SCAN:LSEL INT", # Enable scan.
            'FORM:ELEM READ',#, UNIT, TST, CHAN, LIM' #lots of spare data, for some reason?
        ]
        for cmd in comArray:
            dmm.write(cmd)
            time.sleep(0.1)
        voltage=dmm.query_ascii_values('READ?')[0]
    
    setup = [
        '*RST', # resets the device
        'TRAC:CLE', # clears the buffer
        "ROUT:OPEN:ALL", # makes sure all connections on the multiplexer are open (disconnected)
        "ROUT:CLOS (@125)", # connects the middle pin of the array plate to the meter
        "FUNC 'VOLT',(@125)", # makes sure it's a voltage reading we are taking.
        "INIT:CONT ON", # continuously sample so get updates on front panel.
        'FORM:ELEM READ',#, UNIT, TST, CHAN, LIM' #lots of spare data, for some reason?
    ]
    for cmd in setup:
        dmm.write(cmd)
        time.sleep(0.1)

    if read:
        return voltage
    else:
        return None

def read_voltages(dmm,centre5x5 = False, delay=0):
    """
    Scans 49 channels of a keithley 2701 DMM and returns the resposnes as an array
    (7x7)
    """
    setup = [
        '*RST',
        'TRAC:CLE',
        "ROUT:OPEN:ALL", # makes sure all connections on the multiplexer are open (disconnected)
        'FORM:ELEM READ'#, UNIT, TST, CHAN, LIM' #lots of spare data, for some reason?
    ]   
    voltage_setup = []
    if centre5x5:
        voltage_setup = [
            'TRAC:CLE',
            'INIT:CONT OFF',
            'SENS:FUNC "VOLT", (@109:113,116:120,123:127,130:134,137:140,201)',
            'ROUT:SCAN (@109:113,116:120,123:127,130:134,137:140,201)',
            'TRIG:COUN 1',
            'TRIG:DEL '+str(delay),
            'SAMP:COUN 25',
            'TRIG:SOUR IMM',
            'ROUT:SCAN:LSEL INT',
        ]
    else:
        voltage_setup = [
            'TRAC:CLE',
            'INIT:CONT OFF',
            'SENS:FUNC "VOLT", (@101:140,201:209)',
            'ROUT:SCAN (@101:140,201:209)',
            'TRIG:COUN 1',
            'TRIG:DEL '+str(delay),
            'SAMP:COUN 49',
            'TRIG:SOUR IMM',
            'ROUT:SCAN:LSEL INT',
        ]

    for cmd in [*setup,*voltage_setup]:
        dmm.write(cmd)
        time.sleep(0.1)
    

    voltages=dmm.query_ascii_values('READ?')
    # voltages = [voltages[7*i:7*i+7] for i in range(7)] # reshape to 2d list
    # 
    voltages=np.array(voltages)
    if centre5x5:
        voltages=voltages.reshape([5,5])
    else:
        voltages=voltages.reshape([7,7])

    readMiddlePin(dmm)
    if voltages.any()>1E10:
        return 'error'

    return voltages 



def plotBase(readings, height = 600, width = 600, title = ''):
    # rArray=np.array(readings)
    # rArray=rArray.reshape([7,7])
    layout = go.Layout(
        title = title,
        title_font_color="#BCCCDC",
        height=600,
        width=600,
    )

    fig = go.Figure(data =
        go.Contour(
            colorscale='RdBu',
            z=readings,
            # zauto = False,
            zmin=-np.max(np.abs(readings)),
            zmax=np.max(np.abs(readings)),
            zmid=0,
            ncontours=21,
        ),
        layout = layout
    )
    if len(readings) == 5:
        x = np.array([n for n in range(5) for n in range(5)])
        y = np.array([i for i in range(5) for n in range(5)])
    else:
        x = np.array([n for n in range(7) for n in range(7)])
        y = np.array([i for i in range(7) for n in range(7)])
    fig.add_scatter(x=x,y=y, mode='markers',
                    marker = dict(color = 'rgb(0, 0, 0)', size = 5,)
                   )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        title={
    #         'text': "Plot Title",
            'y':0.84,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'},
        xaxis = {
            'showgrid' : False,
            'tickmode' :'linear',
            'showticklabels':False,
        },
        yaxis = {
            'showgrid' : False,
            'showticklabels':False,
        }
    )
    # fig.show()
    return fig
        
def plotV(voltages, height = 600, width = 600):
    fig = plotBase(voltages, height = height, width = width, title = 'Voltage Map (V)')
    return fig

def plotI(currents, height = 600, width = 600):
    fig = plotBase(currents, height = height, width = width, title = r"$\text{Current Distribution (mA/cm}^2\text{)}$")
    return fig


class arrayPlateMeasurement:
    def __init__(self):
        self.data = list()
        self.dmm = None

    def connect(self):
        try:
            self.dmm = connectKeithley()
        except:
            print("Device not found. Try running 'disconnectVisa()'.")

    def disconnect(self):
        try:
            disconnectKeithley(self.dmm)
        except:
            disconnectVisa()
            print("Might have accidentally disconnected all visa devices.")
    
    def append(self, **entry):
        entry['time'] = getTimeStr()#time.asctime()
        try:
            entry['currents'] = entry['currents'].tolist()
        except:
            pass
        try:
            entry['voltages'] = entry['voltages'].tolist()
        except:
            pass
        self.data.append(entry)
        print(f'Number of entries: {len(self.data)}')
    
    def readVoltages(self, centre5x5 = False):
        voltages = read_voltages(self.dmm, centre5x5)
        return voltages

    def readCurrents(self, centre5x5 = False):
        area = (11.72/10/2)**2*np.pi
        voltages = read_voltages(self.dmm, centre5x5)
        currents = voltages * 10 /area
        # currents = [voltage*10/area for voltage in read_voltages(self.dmm)]
        return currents

    def deleteLast(self):
        self.data.pop()
        print(f'Number of entries: {len(self.data)}')
    
    def delete(self, entry = -1):
        return self.data.pop(entry)

    def save(self, fHeader):
        if (self.len() > 0):
            fName = fHeader + '_' + getTimeStr() + '.json'
            saveString = json.dumps(self.data, indent=4)
            # print(saveString)
            saveString = roundSigFig(saveString, 4)
            # print()
            print(fName)
            with open(fName, 'w') as outfile:
                outfile.write(saveString)
                # json.dump(self.data, outfile, indent=4)
    
    def load(self, fName):
        self.data = list()
        try:
            with open(fName, 'r') as infile:
                d = json.load(infile)
                for entry in d:
                    self.data.append(entry)
            print(self.len(), 'entries loaded.')
        except:
            print("File not found.")
    
    def len(self):
        return len(self.data)
    
    def plotV(self, entry = -1):
        fig = plotV(self.data[entry]['voltages'])
        return fig

    def plotI(self, entry = -1):
        fig = plotI(self.data[entry]['currents'])
        return fig

''' Use example

import ArrayPlateLogger as apl

data = apl.arrayPlateMeasurement()
data.connect()

currents = data.readCurrents()
data.append(
    pressure = 1.7e-4,
    Vbias = 120,
    Ibias = 67,
    Varc = 80,
    Iarc = 2.25,
    Vext = 40,
    Iext = 10.0,
    currents = currents,
    note = 'Put something useful here.')
data.plotI()

data.disconnect() 
'''