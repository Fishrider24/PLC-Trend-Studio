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
import json
from paths import WORKSPACE_PATH, DATA_PATH, REPORT_PATH
from collections import deque

# Live history settings
MEMORY_MINUTES = 30        # Change to 30 for production

def readPLCTags(ipAddress, nameOfTag, dataFileName, commandQueue, liveQueue):
    """Takes ipAddress, nameOfTag and dataFileName and reads tag values then uses
    dataWriter() to write them to .csv files.  Adjust time.sleep() to change
    the sampling time."""
    with PLC() as comm:
        comm.IPAddress = ipAddress
        while True:
            try:
                while not commandQueue.empty():
                    command = commandQueue.get()
                    if command["type"] == "ADD_TAG":
                        nameOfTag.append(command["tag"])
                        dataFileName.append(command["file"])
                ret = comm.Read(nameOfTag)
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
                        timestamp,
                        ret
                    )
                )
                #dataPickler(ret, dataFileName)
                time.sleep(0.02)
            except KeyboardInterrupt:
                break

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
        import errno
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

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, dataFileName, nameOfTag, ipAddress, commandQueue, liveQueue, plcProcess):
        super(MainWindow, self).__init__()
        self.commandQueue = commandQueue
        self.liveQueue = liveQueue
        self.plcProcess = plcProcess
        self.historyMode = False
        self.historyLoaded = False
        #self.axisDialog = AxisScalingDialog(self)
        self.nameOfTag = nameOfTag
        self.dataFileName = dataFileName
        # Remember PLC IP
        self.ipAddress = ipAddress
#        self.lastFileSize = []
#        for filename in self.dataFileName:
#            self.lastFileSize.append(0)
# Make sure Workspaces folder exists
        self.workspaceFile = os.path.join(
            WORKSPACE_PATH,
            self.ipAddress.replace(".", "_") + ".json"
        )
        #self.graphWidget = pg.PlotWidget(axisItems = {'bottom': pg.DateAxisItem()})
        #self.setCentralWidget(self.graphWidget)
        #self.plotitem = self.graphWidget.getPlotItem()
        #self.graphWidget.addLegend()
        self.graphWidget = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        self.setCentralWidget(self.graphWidget)
    # Trace Manager Dock
        self.traceDock = QtWidgets.QDockWidget("Traces", self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
            self.traceDock
        )
        self.traceTree = QtWidgets.QTreeWidget()
        self.traceTree.setColumnCount(4)
        self.traceTree.setHeaderLabels([
            "",
            "Tag",
            "Value",
            "Axis"
        ])
        self.traceTree.setColumnWidth(0, 10)
        self.traceTree.setColumnWidth(1, 140)
        self.traceTree.setColumnWidth(2, 50)
        self.traceTree.setColumnWidth(3, 10)
        self.traceTree.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.traceTree.customContextMenuRequested.connect(
            self.traceContextMenu
        )
        self.traceDock.setWidget(self.traceTree)
        # ---------- Menu Bar ----------
        menubar = self.menuBar()
    # File Menu
        fileMenu = menubar.addMenu("File")
        loadWorkspace = QtGui.QAction("Load Workspace...", self)
        saveWorkspace = QtGui.QAction("Save Workspace...", self)
        fileMenu.addAction(loadWorkspace)
        fileMenu.addAction(saveWorkspace)
        loadWorkspace.triggered.connect(self.loadWorkspace)
        saveWorkspace.triggered.connect(self.saveWorkspace)
    # Settings Menu
        settingsMenu = menubar.addMenu("Settings")
        axisScaling = QtGui.QAction("Axis Scaling...", self)
        settingsMenu.addAction(axisScaling)
        axisScaling.triggered.connect(self.showAxisScaling)
    # Add PLC Tag
        addTagAction = QtGui.QAction("Add PLC Tag...", self)
        settingsMenu.addSeparator()
        settingsMenu.addAction(addTagAction)
        addTagAction.triggered.connect(self.addPLCTag)
        self.plotitem = self.graphWidget.getPlotItem()
    # Time Menu
        viewMenu = menubar.addMenu("View")
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
        min30 = timeMenu.addAction("30 Minutes")
        hr1 = timeMenu.addAction("1 Hour")
        sec30.triggered.connect(lambda: self.setTimeWindow(30))
        min1.triggered.connect(lambda: self.setTimeWindow(60))
        min2.triggered.connect(lambda: self.setTimeWindow(120))
        min5.triggered.connect(lambda: self.setTimeWindow(300))
        min10.triggered.connect(lambda: self.setTimeWindow(600))
        min30.triggered.connect(lambda: self.setTimeWindow(1800))
        hr1.triggered.connect(lambda: self.setTimeWindow(3600))
       # Existing left axis
        self.leftView = self.plotitem.vb
       # Create a second ViewBox for the right axis
        self.rightView = pg.ViewBox()
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
        self.createRightAxis()
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
        self.axisItems[2].setTextPen((0,255,0))
        self.axisItems[2].setPen((0,255,0))
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
        self.statusBar.addPermanentWidget(self.statusConnection)
        self.statusBar.addPermanentWidget(self.statusTags)
        self.statusBar.addPermanentWidget(self.statusWindow)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(500)
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
    # Add curve to correct axis
        self.axisViews[axis].addItem(curve)
    # Build curve information
        index = len(self.curves)
        curveInfo = {
            "curve": curve,
            "axis": axis,
            "tag": tagName,
            "index": index,
            "visible": True,
            "style": QtCore.Qt.PenStyle.SolidLine
        }
        self.graphs.append(curve)
        self.curves.append(curveInfo)
    # Add row to Trace Manager
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, "⬤")
        item.setText(1, tagName)
        item.setText(2, "")
        item.setText(3, self.axisName(axis))
        self.traceTree.addTopLevelItem(item)
    #    self.traceItems.append(item)
        item.setTextAlignment(
            2,
            QtCore.Qt.AlignmentFlag.AlignRight |
            QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        item.setTextAlignment(
            0,
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        item.setTextAlignment(
            3,
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
        while not self.liveQueue.empty():
            timestamp, ret = self.liveQueue.get()
            for r in ret:
                value = r.Value
                if value is True:
                    value = 1000
                elif value is False:
                    value = 0
    # Ignore tags we don't know about yet
                if r.TagName not in self.liveHistory:
                    continue
                self.liveHistory[r.TagName]["time"].append(timestamp)
                self.liveHistory[r.TagName]["value"].append(value)
    # Remove anything older than the memory window
                cutoff = timestamp - MEMORY_MINUTES * 60
                history = self.liveHistory[r.TagName]
                while (
                    history["time"]
                    and history["time"][0] < cutoff
                ):
                    history["time"].popleft()
                    history["value"].popleft()
    # Update curves from memory
        latestTime = 0
        for i in range(len(self.nameOfTag)):
            tag = self.nameOfTag[i]
            if self.historyMode:
                history = self.historyCache[tag]
            else:
                history = self.liveHistory[tag]
    # Nothing received yet
            if len(history["time"]) == 0:
                continue
    # Draw graph
            self.curves[i]["curve"].setData(
                history["time"],
                history["value"]
            )
    # Current value
            currentValue = history["value"][-1]
            self.curves[i]["item"].setText(
                2,
                f"{currentValue:.2f}"
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
            3,
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
                c["curve"].setPen(pen)
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
        dashAction = styleMenu.addAction("Dashed")
        dotAction = styleMenu.addAction("Dotted")
        dashDotAction = styleMenu.addAction("Dash-Dot")
        actions = {}
        for axis in range(len(self.axisViews)):
            action = moveMenu.addAction(
                self.axisName(axis)
            )
            actions[action] = axis
        moveMenu.addSeparator()
        newAxisAction = moveMenu.addAction(
            "New Right Axis..."
        )
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
        filename = self.workspaceFile
        if not filename:
            return
        workspace = {
            "application": "PLC Trend Studio",
            "version": "6.3",
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
                "axis": c["axis"],
                "visible": c["visible"],
                "style": c["style"].value
            })
        with open(filename, "w") as f:
            json.dump(
                workspace,
                f,
                indent=4
            )

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
    # Make sure enough axes exist
        highestAxis = 0
        for trace in workspace["traces"]:
            highestAxis = max(
                highestAxis,
                trace["axis"]
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
    # Restore trace positions
        for trace in workspace["traces"]:
            for i, c in enumerate(self.curves):
                if c["tag"] == trace["tag"]:
                    if "style" in trace:
                        c["style"] = QtCore.Qt.PenStyle(trace["style"])
                    self.moveCurve(
                        i,
                        trace["axis"]
                    )
                    if trace["visible"] != c["visible"]:
                        self.toggleCurve(i)
                    break

    def closeEvent(self, event):
        self.saveWorkspace()
        self.plcProcess.terminate()
        self.plcProcess.join(2)
        super().closeEvent(event)

    def updateStatusBar(self):
        self.statusConnection.setText(
            f"PLC: {self.ipAddress}"
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

    def addPLCTag(self):
       
        tagName, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add PLC Tag",
            "PLC Tag:"
        )
        if not ok:
            return
        if not tagName:
           return
    # Don't add duplicates
        if tagName in self.nameOfTag:
            QtWidgets.QMessageBox.information(
                self,
                "Already Exists",
                f"{tagName} is already being trended."
            )
            return
    # Create CSV filename
        fileName = ui.dataFileCreation(
            self.ipAddress,
            tagName
        )
    # Default to Right 1
        axis = 1
    # Update program lists
        tagName = tagName.strip()
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
    # Create everything
        self.createCurve(
            tagName,
            fileName,
            axis
        )
        self.recolorCurves()
        self.updateStatusBar()
        self.commandQueue.put({
            "type": "ADD_TAG",
            "tag": tagName,
            "file": fileName
        })
        ui.savePreviousTags(self.ipAddress, self.nameOfTag)
        
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
    # Save updated PreviousTags
        ui.savePreviousTags(self.ipAddress, self.nameOfTag)
        self.recolorCurves()
        self.updateStatusBar()

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
                    "time": deque(data[:,0]),
                    "value": deque(data[:,1])
                }
            except Exception:
                self.historyCache[tag] = {
                    "time": deque(),
                    "value": deque()
                }

def main():
    parent_conn, child_conn = mp.Pipe()
    i = 0
    dataFileName = []
    ipAddress = ui.ipName()
    previousTagName = ui.usePreviousTag(ipAddress)
    if previousTagName == False:
        nameOfTag = ui.tagName()
        nameOfTag = ui.tagCheck(ipAddress, nameOfTag)
    else:
        nameOfTag = previousTagName
    for k in nameOfTag:
        dataFileName.append(
            ui.dataFileCreation(
                ipAddress,
                k
            )
        )
    #    dataFileName.append(ui.dataPickleCreation(k))
    commandQueue = mp.Queue()
    liveQueue = mp.Queue()
    p1 = mp.Process(
        target = readPLCTags,
         args = (
            ipAddress,
            nameOfTag,
            dataFileName,
            commandQueue,
            liveQueue
            ))
    p1.start()
    time.sleep(3)
     
    app = QtWidgets.QApplication(sys.argv)
    for filename in dataFileName:
        while os.path.getsize(filename) == 0:
            time.sleep(0.05)
#    for filename in dataFileName:
#        while True:
#            try:
#                df = pd.read_csv(filename)
#                if len(df):
#                    break
#            except (
#                pd.errors.EmptyDataError,
#                FileNotFoundError
#            ):
#                pass
#            time.sleep(0.05)
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
