from pylogix import PLC
import datetime
import time
import csv
import User_Interface as ui
import multiprocessing as mp
import pandas as pd
import numpy as np
import sys
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QColor
import pyqtgraph as pg
import os
from random import randint
import pickle
import json
from paths import WORKSPACE_PATH, DATA_PATH, REPORT_PATH
from collections import deque
import bisect
import math

def readPLCTags(ipAddress, nameOfTag, dataFileName, commandQueue, liveQueue):
    """Takes ipAddress, nameOfTag and dataFileName and reads tag values then uses
    dataWriter() to write them to .csv files.  Adjust time.sleep() to change
    the sampling time."""
    connected = False
    reconnecting = False
    sampleInterval = 20
    while True:
        try:
            with PLC() as comm:
                comm.IPAddress = ipAddress
                result = comm.GetDeviceProperties()
                if result.Status == "Success" and not connected:
                    connected = True
                    reconnecting = False
                    print(f"Connected to {ipAddress}")
                    liveQueue.put(
                        (
                            "CONNECTED",
                            time.time(),
                            None
                        )
                    )
                while True:
                    while not commandQueue.empty():
                        command = commandQueue.get()
                        if command["type"] == "ADD_TAG":
                            nameOfTag.append(command["tag"])
                            dataFileName.append(command["file"])
                        elif command["type"] == "SET_SAMPLE_INTERVAL":
                            sampleInterval = command["value"]
                    if not nameOfTag:
                        time.sleep(0.05)
                        continue
                    try:
                        ret = comm.Read(nameOfTag)
                    except Exception as e:
                        if connected:
                            print("Connection lost.")
                            connected = False
                            reconnecting = False
                        liveQueue.put(
                            (
                                "DISCONNECT",
                                time.time(),
                                None
                            )
                        )
                        break
                # Check if PyLogix reported a bad read
                    badRead = False
                    for r in ret:
                        if r.Status != "Success":
                            if connected:
                                print("Connection lost.")
                                connected = False
                                reconnecting = False
                            badRead = True
                            break
                    if badRead:
                        if connected:
                            print("Connection lost.")
                            connected = False
                            reconnecting = False
                        liveQueue.put(
                            (
                                "DISCONNECT",
                                time.time(),
                                None
                            )
                        )
                        break
                    if not connected:
                        print(f"Connected to {ipAddress}")
                        connected = True
                        reconnecting = False
                        liveQueue.put(
                            (
                                "CONNECTED",
                                time.time(),
                                None
                            )
                        )
                    dataWriter(ret, dataFileName)
                    timestamp = time.time()
        # Normalize values once
                    for r in ret:
                        if r.Value is True:
                            r.Value = 1
                        elif r.Value is False:
                            r.Value = 0
        # Queue ONE complete PLC scan
                    liveQueue.put(
                        (
                            "DATA",
                            timestamp,
                            ret
                        )
                    )
                    time.sleep(
                        sampleInterval / 1000
                    )
        except Exception as e:
            print("PLC Exception:", e)
        # Wait before reconnecting
        if not connected and not reconnecting:
            print("Attempting to reconnect...")
            reconnecting = True
        time.sleep(1)

def dataWriter(ret, dataFileName):
 
    """Takes ret values from PLC comm.Read and dataFileName to write time
    and data values to the individual csv files"""
    timestamp = time.time()
    offset = 0
    for r in ret:
        if r.Value is True:
            r.Value = 1
        elif r.Value is False:
            r.Value = 0
        data = [timestamp, r.Value]
        for retry in range(10):
            try:
                with open(dataFileName[offset], 'a', encoding='UTF8') as f:
                    writer = csv.writer(f)
                    writer.writerow(data)
                break
            except PermissionError as e:
                print(
                    "Retry",
                    retry,
                    dataFileName[offset]
                )
                time.sleep(0.01)
                if retry == 9:
                    raise
        #with open(dataFileName[offset], 'a', encoding='UTF8') as f:
        #    writer = csv.writer(f)
        #    writer.writerow(data)
        offset += 1

class TrendItemSample(pg.graphicsItems.LegendItem.ItemSample):

    def __init__(self, item, index, mainWindow):
        super().__init__(item)
        self.index = index
        self.mainWindow = mainWindow
    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            self.mainWindow.showCurveMenu(
                self.index,
                ev.screenScreenPos().toPoint()
            )
            ev.accept()
        else:
            super().mouseClickEvent(ev)

class AxisScalingDialog(QtWidgets.QDialog):

    def __init__(self, axisNames, parent=None):

        super().__init__(parent)
        self.setWindowTitle("Axis Scaling")
        layout = QtWidgets.QGridLayout(self)
        self.axes = []
        row = 0
        for axisName in axisNames:
            group = QtWidgets.QGroupBox(axisName)
            g = QtWidgets.QGridLayout(group)
            auto = QtWidgets.QCheckBox("Auto Scale")
            auto.setChecked(True)
            minEdit = QtWidgets.QLineEdit("0")
            maxEdit = QtWidgets.QLineEdit("100")
            g.addWidget(auto,0,0,1,2)
            g.addWidget(QtWidgets.QLabel("Minimum"),1,0)
            g.addWidget(minEdit,1,1)
            g.addWidget(QtWidgets.QLabel("Maximum"),2,0)
            g.addWidget(maxEdit,2,1)
            layout.addWidget(group,row,0)
            self.axes.append({
                "auto":auto,
                "min":minEdit,
                "max":maxEdit
            })
            row += 1
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons,row,0)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

class DataCollectionDialog(QtWidgets.QDialog):
    def __init__(self, sampleInterval,
                 memoryMinutes,
                 displayInterval,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Collection")
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Sample Interval (ms)"),
            0,0
        )
        self.sampleEdit = QtWidgets.QLineEdit(
            str(sampleInterval)
        )
        layout.addWidget(
            self.sampleEdit,
            0,1
        )
        layout.addWidget(
            QtWidgets.QLabel("Default: 20 ms"),
            0,2
        )
        layout.addWidget(
            QtWidgets.QLabel("Live Data in Ram (minutes)"),
            1,0
        )
        self.memoryEdit = QtWidgets.QLineEdit(
            str(memoryMinutes)
        )
        layout.addWidget(
            self.memoryEdit,
            1,1
        )
        layout.addWidget(
            QtWidgets.QLabel("Default: 30 min"),
            1,2
        )
        layout.addWidget(
            QtWidgets.QLabel("Display Update (ms)"),
            2,0
        )
        self.displayEdit = QtWidgets.QLineEdit(
            str(displayInterval)
        )
        layout.addWidget(
            self.displayEdit,
            2,1
        )
        layout.addWidget(
            QtWidgets.QLabel("Default: 500 ms"),
            2,2
        )
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(
            buttons,
            3,0,1,2
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, dataFileName, nameOfTag, ipAddress, commandQueue, liveQueue, plcProcess):
        super(MainWindow, self).__init__()
        self.connectionState = "Connecting"
        settings = ui.loadSettings()
        self.sampleInterval = settings["sampleInterval"]
        self.memoryMinutes = settings["memoryMinutes"]
        self.displayInterval = settings["displayInterval"]
        self.commandQueue = commandQueue
        self.liveQueue = liveQueue
        self.plcProcess = plcProcess
        self.historyMode = False
        self.historyLoaded = False
        self.graphDirty = True
        self.historyDirty = True
        self.cursorActive = False
        self.nameOfTag = nameOfTag
        self.dataFileName = dataFileName
        # Remember PLC IP
        self.ipAddress = ipAddress
# Make sure Workspaces folder exists
        self.workspaceFile = os.path.join(
            WORKSPACE_PATH,
            self.ipAddress.replace(".", "_") + ".json"
        )
        self.graphWidget = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        self.setCentralWidget(self.graphWidget)
    # Trace Manager Dock
        self.traceDock = QtWidgets.QDockWidget("Traces", self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
            self.traceDock
        )
        self.traceTree = QtWidgets.QTreeWidget()
        self.traceTree.setColumnCount(5)
        self.traceTree.setHeaderLabels([
            "",
            "",
            "Tag",
            "Value",
            "Axis"
        ])
        self.traceTree.setColumnWidth(0, 50)
        self.traceTree.setColumnWidth(1, 10)
        self.traceTree.setColumnWidth(2, 140)
        self.traceTree.setColumnWidth(3, 50)
        self.traceTree.setColumnWidth(4, 10)
        self.traceTree.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.traceTree.customContextMenuRequested.connect(
            self.traceContextMenu
        )
        self.traceDock.setWidget(self.traceTree)
        self.traceDock.setMinimumWidth(320)
        # ---------- Menu Bar ----------
        menubar = self.menuBar()
    # File Menu
        fileMenu = menubar.addMenu("File")
        loadWorkspace = QtGui.QAction("Load Workspace...", self)
        saveWorkspace = QtGui.QAction("Save Workspace", self)
        saveWorkspaceAs = QtGui.QAction("Save Workspace As...", self)
        saveSnapshot = QtGui.QAction("Save Snapshot...", self)
        fileMenu.addAction(loadWorkspace)
        fileMenu.addAction(saveWorkspace)
        fileMenu.addAction(saveWorkspaceAs)
        fileMenu.addSeparator()
        fileMenu.addAction(saveSnapshot)
        loadWorkspace.triggered.connect(lambda checked: self.loadWorkspace())
        saveWorkspace.triggered.connect(lambda checked: self.saveWorkspace())
        saveWorkspaceAs.triggered.connect(lambda checked: self.saveWorkspaceAs())
        saveSnapshot.triggered.connect(self.saveSnapshot)
    # Settings Menu
        settingsMenu = menubar.addMenu("Settings")
        axisScaling = QtGui.QAction("Axis Scaling...", self)
        settingsMenu.addAction(axisScaling)
        axisScaling.triggered.connect(self.showAxisScaling)
        dataCollection = QtGui.QAction(
            "Data Collection...",
            self
        )
        settingsMenu.addAction(
            dataCollection
        )
        dataCollection.triggered.connect(
            self.showDataCollection
        )
    # Add PLC Tag
        addTagAction = QtGui.QAction("Add PLC Tag...", self)
        settingsMenu.addSeparator()
        settingsMenu.addAction(addTagAction)
        addTagAction.triggered.connect(self.addPLCTag)
        self.plotitem = self.graphWidget.getPlotItem()
        self.plotitem.showGrid(
            x=True,
            y=True,
            alpha=0.3
        )
        self.plotitem.ctrlMenu = None
        self.graphWidget.scene().contextMenu = None
        self.plotitem.vb.setMenuEnabled(False)
    # Add Curser
        self.cursorLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(
                (255,255,0),
                width=2
            )
        )
        self.cursorLine.hide()
    # Mouse Movement
        self.plotitem.addItem(self.cursorLine)
        self.graphWidget.scene().sigMouseMoved.connect(
            self.mouseMoved
        )
    # Time Menu
        viewMenu = menubar.addMenu("View")
        self.gridAction = QtGui.QAction("Grid", self)
        self.gridAction.setCheckable(True)
        self.gridAction.setChecked(True)
        viewMenu.addAction(self.gridAction)
        self.gridAction.triggered.connect(
            self.toggleGrid
        )
        self.liveModeAction = QtGui.QAction("Live Mode", self)
        self.liveModeAction.setCheckable(True)
        self.liveModeAction.setChecked(True)
        viewMenu.addAction(self.liveModeAction)
        viewMenu.addSeparator()
        self.liveModeAction.triggered.connect(self.toggleLiveMode)
        timeMenu = viewMenu.addMenu("Time Window")
        sec30 = timeMenu.addAction("30 Seconds")
        min1 = timeMenu.addAction("1 Minute")
        min2 = timeMenu.addAction("2 Minutes")
        min5 = timeMenu.addAction("5 Minutes")
        min10 = timeMenu.addAction("10 Minutes")
        min15 = timeMenu.addAction("15 Minutes")
        min20 = timeMenu.addAction("20 Minutes")
        min30 = timeMenu.addAction("30 Minutes")
        hr1 = timeMenu.addAction("1 Hour")
        sec30.triggered.connect(lambda: self.setTimeWindow(30))
        min1.triggered.connect(lambda: self.setTimeWindow(60))
        min2.triggered.connect(lambda: self.setTimeWindow(120))
        min5.triggered.connect(lambda: self.setTimeWindow(300))
        min10.triggered.connect(lambda: self.setTimeWindow(600))
        min15.triggered.connect(lambda: self.setTimeWindow(900))
        min20.triggered.connect(lambda: self.setTimeWindow(1200))
        min30.triggered.connect(lambda: self.setTimeWindow(1800))
        hr1.triggered.connect(lambda: self.setTimeWindow(3600))
       # Existing left axis
        self.leftView = self.plotitem.vb
        self.leftView.setMenuEnabled(False)
       # Create a second ViewBox for the right axis
        self.rightView = pg.ViewBox()
        self.rightView.setMenuEnabled(False)
        self.plotitem.scene().addItem(self.rightView)
        self.plotitem.showAxis('right')
        self.plotitem.getAxis('right').linkToView(self.rightView)
        self.rightView.setXLink(self.leftView)
        # Axis ViewBoxes
# 0 = Left 1
# 1 = Left 2 (future)
# 2 = Right 1
# 3 = Right 2 (future)
        self.axisViews = [
            self.leftView,
            self.rightView,
        ]
        self.axisItems = [
            self.plotitem.getAxis("left"),
            self.plotitem.getAxis("right")
        ]
        
        # Axis settings
    # 0 = Left 1
    # 1 = Left 2
    # 2 = Right 1
    # 3 = Right 2
        self.axisAuto = [True, True, True]
    # Time Window (seconds)
        self.timeWindow = 300      # 5 minutes
        self.updatingRange = False
    # Auto-scroll enabled
        self.autoScroll = True
        self.axisMin  = [0, 0, 0]
        self.axisMax  = [100, 100, 100]
#        self.createRightAxis()
        #self.graphWidget.addLegend()
#        self.legend = self.graphWidget.addLegend()
# Keep both views synchronized
        self.leftView.sigRangeChangedManually.connect(
            self.viewRangeChanged
        )
        self.leftView.sigResized.connect(
            self.updateViews
        )
        self.basePens = [
            pg.mkPen((255,0,0), width=2),      # Red
            pg.mkPen((0,128,255), width=2),    # Blue
            pg.mkPen((0,220,0), width=2),      # Green
            pg.mkPen((180,120,0), width=2),    # Brown
            pg.mkPen((180,0,255), width=2),    # Purple
            pg.mkPen((0,180,180), width=2),    # Cyan
        ]
        #self.linecolors = ['r', 'w', 'g', 'b', 'c', 'm', 'y', pen1, pen2, pen3, pen4, pen5]
        self.graphWidget.setClipToView(True)
        graphs = []
        self.graphs = graphs
        self.axisAssignment = []
        for i in range(len(dataFileName)):
            if i == 0:
                axis = 0            # Left
            elif i % 2 == 1:
                axis = 1            # Right 1
            else:
                axis = 2            # Right 2
            self.axisAssignment.append(axis)
        self.graphs = []
        self.curves = []
        self.plotitem.getAxis('left').setTextPen((255,0,0))
        self.plotitem.getAxis('left').setPen((255,0,0))
        self.plotitem.getAxis('right').setTextPen((0,128,255))
        self.plotitem.getAxis('right').setPen((0,128,255))
    #    self.traceItems = []
        for i in range(len(dataFileName)):
            self.createCurve(
                self.nameOfTag[i],
                self.dataFileName[i],
                self.axisAssignment[i]
         )
        self.recolorCurves()
        self.liveHistory = {}
        self.historyCache = {}
        for tag in self.nameOfTag:
            self.liveHistory[tag] = {
                "time": deque(),
                "value": deque()
            }
            self.historyCache[tag] = {
                "time": deque(),
                "value": deque()
            }
        self.updateViews()
    # Status Bar
        self.statusBar = self.statusBar()
        self.statusConnection = QtWidgets.QLabel()
        self.statusTags = QtWidgets.QLabel()
        self.statusWindow = QtWidgets.QLabel()
        self.statusCursor = QtWidgets.QLabel()
        self.statusBar.addPermanentWidget(self.statusConnection)
        self.statusBar.addPermanentWidget(self.statusTags)
        self.statusBar.addPermanentWidget(self.statusWindow)
        self.statusBar.addPermanentWidget(self.statusCursor)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(
            self.displayInterval
        )
        self.timer.timeout.connect(self.update)
        self.timer.start()
        self.updateStatusBar()

    def createCurve(self, tagName, fileName, axis):
    # Read any existing data
        try:
            data = pd.read_csv(fileName)
            data = np.array(data)
        except (
            pd.errors.EmptyDataError,
            FileNotFoundError
        ):
            data = np.empty((0, 2))
    # Create the curve
        if len(data):
            curve = pg.PlotDataItem(
                data[:,0],
                data[:,1],
                name=tagName
            )
        else:
            curve = pg.PlotDataItem(
                [],
                [],
                name=tagName
            )
        curve.setClipToView(True)
        curve.setDownsampling(
            ds=None,
            auto=True,
            method="peak"
        )
    # Add curve to correct axis
        self.axisViews[axis].addItem(curve)
    # Build curve information
        index = len(self.curves)
        curveInfo = {
            "curve": curve,
            "axis": axis,
            "tag": tagName,
            "displayName": tagName,
            "index": index,
            "visible": True,
            "style": QtCore.Qt.PenStyle.SolidLine,
            "decimals": -1,
            "pen": None,
            "lastStart": -1,
            "lastEnd": -1
        }
        self.graphs.append(curve)
        self.curves.append(curveInfo)
    # Add row to Trace Manager
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, "━━")
        item.setText(1, "⬤")
        item.setText(2, curveInfo["displayName"])
        item.setToolTip(2, tagName)
        item.setText(3, "")
        item.setText(4, self.axisName(axis))
        self.traceTree.addTopLevelItem(item)
    #    self.traceItems.append(item)
        item.setTextAlignment(
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft
        )
        item.setTextAlignment(
            1,
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        item.setTextAlignment(
            3,
            QtCore.Qt.AlignmentFlag.AlignRight |
            QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        item.setTextAlignment(
            4,
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        curveInfo["item"] = item

    def updateViews(self):

        master = self.axisViews[0]
        for vb in self.axisViews:
            if vb is None or vb is master:
                continue
            vb.setGeometry(master.sceneBoundingRect())
            vb.linkedViewChanged(master, vb.XAxis)

    def addAxis(self, side, column):

        vb = pg.ViewBox()
        vb.setMenuEnabled(False)
        ax = pg.AxisItem(side)
        if side == "left":
            ax.setPen('orange')
            ax.setTextPen('orange')
        else:
            ax.setPen('green')
            ax.setTextPen('green')
        self.plotitem.layout.addItem(ax, 2, column)
        self.plotitem.scene().addItem(vb)
        ax.linkToView(vb)
        vb.setXLink(self.leftView)
        return vb, ax

    def update(self):
# Read all queued live data
        if not self.cursorActive:
            now = datetime.datetime.now()
            timeText = now.strftime("%I:%M:%S")
            hundredths = f"{now.microsecond // 10000:02d}"
            ampm = now.strftime("%p")
            self.statusCursor.setText(
                f"Time: {timeText}.{hundredths} {ampm}"
            )
        while not self.liveQueue.empty():
            messageType, timestamp, ret = self.liveQueue.get()
            if messageType == "CONNECTED":
                self.graphDirty = True
                self.connectionState = "🟢 Connected"
                continue
        # Connection lost marker
            if messageType == "DISCONNECT":
                self.graphDirty = True
                self.connectionState = "🔴 DISCONNECTED"
                for history in self.liveHistory.values():
                    history["time"].append(timestamp)
                    history["value"].append(math.nan)
                continue
            for r in ret:
                value = r.Value
                if value is True:
                    value = 1
                elif value is False:
                    value = 0
    # Ignore tags we don't know about yet
                if r.TagName not in self.liveHistory:
                    continue
                self.liveHistory[r.TagName]["time"].append(timestamp)
                self.liveHistory[r.TagName]["value"].append(value)
                self.graphDirty = True
    # Remove anything older than the memory window
                cutoff = timestamp - self.memoryMinutes * 60
                history = self.liveHistory[r.TagName]
                while (
                    history["time"]
                    and history["time"][0] < cutoff
                ):
                    history["time"].popleft()
                    history["value"].popleft()
        latestTime = 0
    # Skip unnecessary redraws
        if self.historyMode:
            if not self.historyDirty and not self.cursorActive:
                return
        else:
            if not self.graphDirty and not self.cursorActive:
                return
        for i in range(len(self.nameOfTag)):
            tag = self.nameOfTag[i]
            if self.historyMode:
                history = self.historyCache[tag]
            else:
                history = self.liveHistory[tag]
    # Nothing received yet
            if len(history["time"]) == 0:
                continue
    # Only plot what is visible
            xmin, xmax = self.leftView.viewRange()[0]
            if self.historyMode:
    # History is already stored as NumPy arrays
                times = history["time"]
                values = history["value"]
            else:
    # Live history is stored in deques
                times = list(history["time"])
                values = list(history["value"])
            start = bisect.bisect_left(
                times,
                xmin
            )
            end = bisect.bisect_right(
                times,
                xmax
            )
            visibleTimes = times[start:end]
            visibleValues = values[start:end]
    # Draw graph
            curveInfo = self.curves[i]
            if (
                self.graphDirty
                or
                curveInfo["lastStart"] != start
                or
                curveInfo["lastEnd"] != end
            ):
                curveInfo["curve"].setData(
                    visibleTimes,
                    visibleValues
                )
                curveInfo["lastStart"] = start
                curveInfo["lastEnd"] = end
    # Current value
            if self.cursorActive:
                cursor = datetime.datetime.fromtimestamp(
                    self.cursorTime
                )
                timeText = cursor.strftime("%I:%M:%S")
                hundredths = f"{cursor.microsecond // 10000:02d}"
                ampm = cursor.strftime("%p")
                self.statusCursor.setText(
                    f"Cursor: {timeText}.{hundredths} {ampm}"
                )
        # Find the closest sample to the cursor
                times = visibleTimes
                index = bisect.bisect_left(
                    times,
                    self.cursorTime
                )
        # Clamp to valid range
#                if index <= 0:
#                    index = 0
#                elif index >= len(times):
#                    index = len(times) - 1
#                else:
        # Cursor is outside available data
                if len(times) == 0:
                    currentValue = None
                elif self.cursorTime < times[0]:
                    currentValue = None
                elif self.cursorTime > times[-1]:
                    currentValue = None
                else:
                    index = bisect.bisect_left(
                        times,
                        self.cursorTime
                    )
                    if index >= len(times):
                        index = len(times) - 1
                    elif index > 0:
                        before = times[index - 1]
                        after = times[index]
                        if abs(self.cursorTime - before) <= abs(after - self.cursorTime):
                            index -= 1
                    currentValue = visibleValues[index]
        # Pick whichever sample is actually closest
#                    before = times[index - 1]
#                    after = times[index]
#                    if abs(self.cursorTime - before) <= abs(after - self.cursorTime):
#                        index -= 1
#                currentValue = visibleValues[index]
            else:
                currentValue = history["value"][-1]
            decimals = self.curves[i]["decimals"]
            if currentValue is None:
                text = "No Data"
            elif decimals == -1:
        # Auto formatting
                try:
                    text = f"{float(currentValue):.6f}".rstrip("0").rstrip(".")
                except (TypeError, ValueError):
                    text = str(currentValue)
            else:
                text = f"{currentValue:.{decimals}f}"
            item = self.curves[i]["item"]
            if item.text(3) != text:
                item.setText(
                    3,
                    text
                )
    # Track newest timestamp
            latestTime = max(
                latestTime,
                history["time"][-1]
            )

        if self.autoScroll and latestTime > 0:
            self.updatingRange = True
            self.leftView.setXRange(
                latestTime - self.timeWindow,
                latestTime,
                padding=0
            )
            self.updatingRange = False
        self.applyAxisScaling()
        self.updateStatusBar()
        self.graphDirty = False
        #self.data_line = self.graphWidget.plot(self.x, self.y)

    def showAxisScaling(self):
        dlg = AxisScalingDialog(
            [self.axisName(i) for i in range(len(self.axisViews))],
            self
        )
        for i in range(len(self.axisViews)):
            dlg.axes[i]["auto"].setChecked(self.axisAuto[i])
            dlg.axes[i]["min"].setText(str(self.axisMin[i]))
            dlg.axes[i]["max"].setText(str(self.axisMax[i]))
        #self.axisDialog.show()
        if dlg.exec():
            for i in range(len(self.axisViews)):
                self.axisAuto[i] = dlg.axes[i]["auto"].isChecked()
                self.axisMin[i] = float(dlg.axes[i]["min"].text())
                self.axisMax[i] = float(dlg.axes[i]["max"].text())
            self.applyAxisScaling()
            self.graphDirty = False
            self.historyDirty = False

    def showDataCollection(self):
        dlg = DataCollectionDialog(
            self.sampleInterval,
            self.memoryMinutes,
            self.displayInterval,
            self
        )
        if dlg.exec():
            self.sampleInterval = int(
                dlg.sampleEdit.text()
            )
            self.memoryMinutes = int(
                dlg.memoryEdit.text()
            )
            self.displayInterval = int(
                dlg.displayEdit.text()
            )
        # Update timer immediately
            self.timer.setInterval(
                self.displayInterval
            )
    # Tell PLC process
        self.commandQueue.put(
            {
                "type":"SET_SAMPLE_INTERVAL",
                "value":self.sampleInterval
            }
        )
        settings = ui.loadSettings()
        settings["sampleInterval"] = self.sampleInterval
        settings["memoryMinutes"] = self.memoryMinutes
        settings["displayInterval"] = self.displayInterval
        ui.saveSettings(settings)

    def applyAxisScaling(self):

    # Existing ViewBoxes
        viewBoxes = self.axisViews
        for i in range(len(self.axisViews)):
         # Axis doesn't exist yet
            if viewBoxes[i] is None:
                continue
            if self.axisAuto[i]:
                viewBoxes[i].enableAutoRange(axis='y')
            else:
                viewBoxes[i].disableAutoRange(axis='y')
                viewBoxes[i].setYRange(
                    self.axisMin[i],
                    self.axisMax[i]
                )

    def setTimeWindow(self, seconds):
        self.timeWindow = seconds
        if self.historyMode:
            self.historyDirty = True
        self.updateStatusBar()
    # If we're paused, resize around the current center
        if not self.autoScroll:
            xmin, xmax = self.leftView.viewRange()[0]
            center = (xmin + xmax) / 2
            half = self.timeWindow / 2
            self.leftView.setXRange(
                center - half,
                center + half,
                padding=0
            )

    def toggleGrid(self):
        enabled = self.gridAction.isChecked()
        self.plotitem.showGrid(
            x=enabled,
            y=enabled,
            alpha=0.3
        )

    def moveCurve(self, curveIndex, newAxis):

        info = self.curves[curveIndex]
        oldAxis = info["axis"]
        if oldAxis == newAxis:
           return
    # Remove from old axis
        self.axisViews[oldAxis].removeItem(info["curve"])
    # Add to new axis
        self.axisViews[newAxis].addItem(info["curve"])
    # Remember new axis
        info["axis"] = newAxis
    # Keep assignments in sync
        self.axisAssignment[curveIndex] = newAxis
        self.curves[curveIndex]["item"].setText(
            4,
            self.axisName(newAxis)
        )
    # Recalculate ALL trace colors
        self.recolorCurves()

    def makeTracePen(self, axis, traceNumber, style):
        base = self.basePens[
            axis % len(self.basePens)
        ]
        color = base.color()
    # First trace
        if traceNumber == 0:
            pen = pg.mkPen(color, width=2)
    # Second trace
        elif traceNumber == 1:
            pen = pg.mkPen(
                color.lighter(140),
                width=2
            )
    # Third trace
        elif traceNumber == 2:
            pen = pg.mkPen(
                color.darker(130),
                width=2
            )
    # Fourth trace
        else:
            pen = pg.mkPen(
                color,
                width=2,
            )
        pen.setStyle(style)
        return pen

    def recolorCurves(self):
        # Go through each axis
        for axis in range(len(self.axisViews)):
        # Build a list of curves on THIS axis
            curvesOnAxis = []
            for c in self.curves:
                if c["axis"] == axis:
                    curvesOnAxis.append(c)
        # Assign colors to the curves on this axis
            for index, c in enumerate(curvesOnAxis):
                pen = self.makeTracePen(
                    axis,
                    index,
                    c["style"]
                )
            # Update graph trace
                oldPen = c["pen"]
                if (
                    oldPen is None
                    or
                    oldPen.color() != pen.color()
                    or
                    oldPen.style() != pen.style()
                ):
                    c["curve"].setPen(pen)
                    c["pen"] = pen
                style = c["style"]
                if style == QtCore.Qt.PenStyle.SolidLine:
                    c["item"].setText(0, "━━")
                elif style == QtCore.Qt.PenStyle.DashLine:
                    c["item"].setText(0, "- - -")
                elif style == QtCore.Qt.PenStyle.DotLine:
                    c["item"].setText(0, "········")
                elif style == QtCore.Qt.PenStyle.DashDotLine:
                    c["item"].setText(0, "-·-·-·")
                if index == 0:
                    self.axisItems[axis].setPen(
                        pen.color()
                    )
                    self.axisItems[axis].setTextPen(
                        pen.color()
                    )
            # Update Trace Manager indicator
                c["item"].setForeground(
                    0,
                    pen.color()
                )
                c["item"].setForeground(
                    1,
                    pen.color()
                )

    def showCurveMenu(self, curveIndex, pos):
        menu = QtWidgets.QMenu()
        left = menu.addAction("Move to Left")
        right1 = menu.addAction("Move to Right 1")
        right2 = menu.addAction("Move to Right 2")
        action = menu.exec(pos)
        if action == left:
            self.moveCurve(curveIndex, 0)
        elif action == right1:
            self.moveCurve(curveIndex, 1)
        elif action == right2:
            self.moveCurve(curveIndex, 2)

    def traceContextMenu(self, position):
        item = self.traceTree.itemAt(position)
        if item is None:
            return
    # Find which row was clicked
        curveIndex = self.traceTree.indexOfTopLevelItem(item)
        menu = QtWidgets.QMenu(self)
        moveMenu = menu.addMenu("Move To")
        styleMenu = menu.addMenu("Line Style")
        solidAction = styleMenu.addAction("Solid")
        solidAction.setCheckable(True)
        if self.curves[curveIndex]["style"] == QtCore.Qt.PenStyle.SolidLine:
            solidAction.setChecked(True)
        dashAction = styleMenu.addAction("Dashed")
        dashAction.setCheckable(True)
        if self.curves[curveIndex]["style"] == QtCore.Qt.PenStyle.DashLine:
            dashAction.setChecked(True)
        dotAction = styleMenu.addAction("Dotted")
        dotAction.setCheckable(True)
        if self.curves[curveIndex]["style"] == QtCore.Qt.PenStyle.DotLine:
            dotAction.setChecked(True)
        dashDotAction = styleMenu.addAction("Dash-Dot")
        dashDotAction.setCheckable(True)
        if self.curves[curveIndex]["style"] == QtCore.Qt.PenStyle.DashDotLine:
            dashDotAction.setChecked(True)
        decimalMenu = menu.addMenu("Decimal Places")
        autoAction = decimalMenu.addAction("Auto")
        autoAction.setCheckable(True)
        if self.curves[curveIndex]["decimals"] == -1:
            autoAction.setChecked(True)
        decimalActions = {
            autoAction: -1
        }
        for d in range(5):
            action = decimalMenu.addAction(str(d))
            action.setCheckable(True)
            if self.curves[curveIndex]["decimals"] == d:
                action.setChecked(True)
            decimalActions[action] = d
        actions = {}
        for axis in range(len(self.axisViews)):
            action = moveMenu.addAction(
                self.axisName(axis)
            )
            action.setCheckable(True)
            if self.curves[curveIndex]["axis"] == axis:
                action.setChecked(True)
            actions[action] = axis
        moveMenu.addSeparator()
        newAxisAction = moveMenu.addAction(
            "New Right Axis..."
        )
        menu.addSeparator()
        renameAction = menu.addAction("Rename Display Name...")
        menu.addSeparator()
        hideAction = menu.addAction("Hide / Show")
        menu.addSeparator()
        removeAction = menu.addAction("Remove Tag")
        action = menu.exec(
            self.traceTree.viewport().mapToGlobal(position)
        )
        if action in actions:
            self.moveCurve(
                curveIndex,
                actions[action]
            )
        elif action == newAxisAction:
    # Create the next axis
            self.createRightAxis()
    # Move the trace there
            self.moveCurve(
                curveIndex,
                len(self.axisViews) - 1
            )
        elif action == renameAction:
            name, ok = QtWidgets.QInputDialog.getText(
                self,
                "Rename Display Name",
                "Display Name:",
                text=self.curves[curveIndex]["displayName"]
            )
            if ok and name.strip():
                self.curves[curveIndex]["displayName"] = name.strip()
                self.curves[curveIndex]["item"].setText(
                    2,
                    name.strip()
                )
        elif action == hideAction:
            self.toggleCurve(curveIndex)
        elif action == removeAction:
            self.removeCurve(curveIndex)
        elif action == solidAction:
            self.curves[curveIndex]["style"] = QtCore.Qt.PenStyle.SolidLine
            self.recolorCurves()
        elif action == dashAction:
            self.curves[curveIndex]["style"] = QtCore.Qt.PenStyle.DashLine
            self.recolorCurves()
        elif action == dotAction:
            self.curves[curveIndex]["style"] = QtCore.Qt.PenStyle.DotLine
            self.recolorCurves()
        elif action == dashDotAction:
            self.curves[curveIndex]["style"] = QtCore.Qt.PenStyle.DashDotLine
            self.recolorCurves()
        elif action in decimalActions:
            self.curves[curveIndex]["decimals"] = decimalActions[action]
            self.update()

    def toggleCurve(self, curveIndex):
        info = self.curves[curveIndex]
        info["visible"] = not info["visible"]
        if info["visible"]:
            self.axisViews[info["axis"]].addItem(
                info["curve"]
            )
            info["item"].setDisabled(False)
        else:
            self.axisViews[info["axis"]].removeItem(
                info["curve"]
            )
            info["item"].setDisabled(True)
        self.recolorCurves()

    def saveWorkspace(self, filename=None):
        if filename is None:
            filename = self.workspaceFile
        if not filename:
            return
        workspace = {
            "application": "PLC Trend Studio",
            "version": "7.2",
            "saved": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ipAddress": self.ipAddress,
            "axes": [],
            "traces": []
        }
    # Save axis settings
        for i in range(len(self.axisAuto)):
            workspace["axes"].append({
                "auto": self.axisAuto[i],
                "min": self.axisMin[i],
                "max": self.axisMax[i]
            })
    # Save traces
        for c in self.curves:
            workspace["traces"].append({
                "tag": c["tag"],
                "displayName": c["displayName"],
                "axis": c["axis"],
                "visible": c["visible"],
                "style": c["style"].value,
                "decimals": c["decimals"]
            })
        with open(filename, "w") as f:
            json.dump(
                workspace,
                f,
                indent=4
            )

    def saveWorkspaceAs(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Workspace As",
            self.workspaceFile,
            "Workspace (*.json)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"
        self.workspaceFile = filename
        self.saveWorkspace(filename)

    def saveSnapshot(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Snapshot",
            "",
            "PNG (*.png)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        pixmap = self.grab()
        pixmap.save(filename)

    def clearGraph(self):
    # Remove curves from the graph
        for c in self.curves:
            self.axisViews[c["axis"]].removeItem(
                c["curve"]
            )
    # Clear Trace Manager
        self.traceTree.clear()
    # Clear program data
        self.curves.clear()
        self.graphs.clear()
        self.nameOfTag.clear()
        self.dataFileName.clear()
        self.axisAssignment.clear()
        self.liveHistory.clear()
        self.historyCache.clear()
        self.updateStatusBar()

    def loadWorkspace(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Workspace",
            os.path.dirname(self.workspaceFile),
            "Workspace (*.json)"
        )
        if not filename:
            return
        self.workspaceFile = filename
        with open(filename, "r") as f:
            workspace = json.load(f)
        while self.curves:
            self.clearGraph()    
    # Make sure enough axes exist
        highestAxis = 0
        for trace in workspace["traces"]:
            self.addTag(
                trace["tag"],
                axis=trace["axis"],
                style=QtCore.Qt.PenStyle(
                    trace["style"]
                ),
                visible=trace["visible"],
                decimals=trace.get("decimals", 2),
                displayName=trace.get("displayName", trace["tag"])
            )
        while len(self.axisViews) <= highestAxis:
            self.createRightAxis()
    # Restore axis settings
        for i, axis in enumerate(workspace["axes"]):
            if i >= len(self.axisViews):
                break
            self.axisAuto[i] = axis["auto"]
            self.axisMin[i] = axis["min"]
            self.axisMax[i] = axis["max"]
        self.applyAxisScaling()

    def closeEvent(self, event):
        self.saveWorkspace()
        self.plcProcess.terminate()
        self.plcProcess.join(2)
        super().closeEvent(event)

    def updateStatusBar(self):
        self.statusConnection.setText(
            f"PLC: {self.ipAddress}    {self.connectionState}"
        )
        self.statusTags.setText(
            f"Tags: {len(self.curves)}"
        )
        minutes = self.timeWindow / 60
        if minutes < 1:
            text = f"{self.timeWindow:.0f} sec"
        elif minutes == 1:
            text = "1 min"
        else:
            text = f"{minutes:.0f} min"
        self.statusWindow.setText(
            f"Window: {text}"
        )

    def firstAvailableAxis(self):
    # Axis 0 is the left axis.
    # Never auto-assign new tags there.
        for axis in range(len(self.axisViews)):
            used = False
            for c in self.curves:
                if c["axis"] == axis:
                    used = True
                    break
            if not used:
                return axis
    # Every existing right axis is occupied.
    # Create a new one.
        return self.createRightAxis()

    def addTag(self, tagName, axis=None, style=QtCore.Qt.PenStyle.SolidLine, visible=True, decimals=-1, displayName=None):
        fileName = ui.dataFileCreation(
            self.ipAddress,
            tagName
        )
    # Automatically choose an axis if one wasn't supplied
        if axis is None:
            axis = self.firstAvailableAxis()
        self.nameOfTag.append(tagName)
        self.dataFileName.append(fileName)
        self.axisAssignment.append(axis)
        self.liveHistory[tagName] = {
            "time": deque(),
            "value": deque()
        }
        self.historyCache[tagName] = {
            "time": deque(),
            "value": deque()
        }
        self.ensureAxisExists(axis)
        self.createCurve(
            tagName,
            fileName,
            axis
        )
    # Restore style
        curve = self.curves[-1]
        if displayName is None:
            displayName = tagName
        curve["displayName"] = displayName
        curve["item"].setText(
            2,
            displayName
        )
        curve["style"] = style
        curve["decimals"] = decimals
        self.recolorCurves()
    # Restore visibility
        if not visible:
            self.toggleCurve(len(self.curves)-1)
        self.updateStatusBar()
        self.commandQueue.put({
            "type": "ADD_TAG",
            "tag": tagName,
            "file": fileName
        })
        return len(self.curves)-1

    def addPLCTag(self):
        tagName, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add PLC Tag",
            "PLC Tag:"
        )
        if not ok:
            return
        tagName = tagName.strip()
        if not tagName:
            return
        if tagName in self.nameOfTag:
            QtWidgets.QMessageBox.information(
                self,
                "Already Exists",
                f"{tagName} is already being trended."
            )
            return
        with PLC(self.ipAddress) as comm:
            ret = comm.Read(tagName)
        if ret.Status != "Success":
            QtWidgets.QMessageBox.warning(
                self,
                "Tag Not Found",
                f"'{tagName}' could not be read.\n\n"
                f"PLC returned:\n{ret.Status}"
            )
            return
        self.addTag(tagName)
        
    def removeCurve(self, curveIndex):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove PLC Tag",
            f"Remove '{self.curves[curveIndex]['tag']}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
    # Remove from graph
        info = self.curves[curveIndex]
        self.axisViews[info["axis"]].removeItem(
            info["curve"]
        )
    # Remove from Trace Manager
        item = info["item"]
        index = self.traceTree.indexOfTopLevelItem(item)
        if index >= 0:
            self.traceTree.takeTopLevelItem(index)
    # Remove from lists
        self.curves.pop(curveIndex)
        self.graphs.pop(curveIndex)
        self.nameOfTag.pop(curveIndex)
        self.dataFileName.pop(curveIndex)
        self.axisAssignment.pop(curveIndex)
    # Re-number remaining curves
        for i, c in enumerate(self.curves):
            c["index"] = i
        self.recolorCurves()
        self.updateStatusBar()

    def deleteUnusedAxes(self):
    # Never delete the Left axis or R1
        axis = 2
        while axis < len(self.axisViews):
    # Does any trace use this axis?
            used = False
            for c in self.curves:
                if c["axis"] == axis:
                    used = True
                    break
    # If unused, remove it
            if not used:
                vb = self.axisViews.pop(axis)
                self.plotitem.scene().removeItem(vb)
                ax = self.axisItems.pop(axis)
                self.plotitem.layout.removeItem(ax)
                self.axisAuto.pop(axis)
                self.axisMin.pop(axis)
                self.axisMax.pop(axis)
    # Don't increment.
    # Another axis shifted into this slot.
                continue
            axis += 1
        self.updateViews()

    def ensureAxisExists(self, axis):
    # Axis 0 is Left.
    # Everything else is a right axis.
        while axis >= len(self.axisViews):
            self.createRightAxis()

    def createRightAxis(self):
        column = len(self.axisViews) + 2
        vb, ax = self.addAxis(
            "right",
            column
        )
        self.axisViews.append(vb)
        self.axisItems.append(ax)
        self.axisAuto.append(True)
        self.axisMin.append(0)
        self.axisMax.append(100)
        self.updateViews()
        return len(self.axisViews)-1

    def axisName(self, axis):
        if axis == 0:
            return "L"
        return f"R{axis}"

    def viewRangeChanged(self):
         # Ignore changes made by our own code
        if self.updatingRange:
            return
    # User moved the graph
        self.autoScroll = False
        self.historyMode = True
        if not self.historyLoaded:
            self.loadHistory()
            self.historyLoaded = True
            self.historyDirty = True
        if hasattr(self, "liveModeAction"):
            self.liveModeAction.setChecked(False)

    def toggleLiveMode(self):
        self.autoScroll = self.liveModeAction.isChecked()
        if self.autoScroll:
            self.historyMode = False
            self.historyCache.clear()
            self.historyLoaded = False
            self.update()
        else:
            self.historyMode = True
            if not self.historyLoaded:
                self.loadHistory()
                self.historyLoaded = True

    def loadHistory(self):
        self.historyCache.clear()
        for i, tag in enumerate(self.nameOfTag):
            try:
                data = pd.read_csv(
                    self.dataFileName[i],
                    engine="c"
                )
                data = np.array(data)
                self.historyCache[tag] = {
                    "time": data[:,0],
                    "value": data[:,1]
                }
            except Exception:
                self.historyCache[tag] = {
                    "time": np.array([]),
                    "value": np.array([])
                }

    # def loadHistory(self):
    #     self.historyCache.clear()
    #     for i, tag in enumerate(self.nameOfTag):
    #         try:
    #             data = pd.read_csv(
    #                 self.dataFileName[i],
    #                 engine="c"
    #             )
    #             data = np.array(data)
    #             self.historyCache[tag] = {
    #                 "time": deque(data[:,0]),
    #                 "value": deque(data[:,1])
    #             }
    #         except Exception:
    #             self.historyCache[tag] = {
    #                 "time": deque(),
    #                 "value": deque()
    #             }

    def mouseMoved(self, pos):
  # Only enable cursor while Ctrl is held
        if not (
            QtWidgets.QApplication.keyboardModifiers()
            &
            QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.cursorLine.hide()
            self.cursorActive = False
            return
  # Convert mouse position into graph coordinates
        mousePoint = self.plotitem.vb.mapSceneToView(pos)
        self.cursorLine.show()
        self.cursorActive = True
  # Remember cursor time
        self.cursorTime = mousePoint.x()
  # Move the vertical cursor
        self.cursorLine.setPos(self.cursorTime)

def main():
    app = QtWidgets.QApplication(sys.argv)
#    parent_conn, child_conn = mp.Pipe()
#    i = 0
    dataFileName = []
  # Ask for a PLC until we get one
    while True:
        settings = ui.loadSettings()
        ipAddress = ui.ipDialog(
            defaultIP=settings["lastIP"]
        )
        if not ipAddress:
            return
        with PLC() as comm:
            comm.IPAddress = ipAddress
            try:
                result = comm.GetDeviceProperties()
            except Exception:
                result = None
        if result is not None and result.Status == "Success":
            settings["lastIP"] = ipAddress
            ui.saveSettings(settings)
            break
        reply = QtWidgets.QMessageBox.question(
            None,
            "PLC Connection Failed",
            f"Unable to communicate with:\n\n"
            f"{ipAddress}\n\n"
            f"Status:\n"
            f"{result.Status if result else 'No Response'}\n\n"
            "Would you like to enter another IP address?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.No:
            return
    nameOfTag = []
    commandQueue = mp.Queue()
    liveQueue = mp.Queue()
    p1 = mp.Process(
        target=readPLCTags,
        args=(
            ipAddress,
            nameOfTag,
            dataFileName,
            commandQueue,
            liveQueue
        )
    )
    p1.start()
#    time.sleep(3)
    w = MainWindow(
        dataFileName,
        nameOfTag,
        ipAddress,
        commandQueue,
        liveQueue,
        p1
    )
    w.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    mp.freeze_support()
    main()
