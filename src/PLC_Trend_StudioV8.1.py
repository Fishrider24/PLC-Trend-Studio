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


def readPLCTags(ipAddress, nameOfTag, dataFileName, commandQueue, liveQueue, sampleInterval):
    """Takes ipAddress, nameOfTag and dataFileName and reads tag values then uses
    dataWriter() to write them to .csv files.  Adjust time.sleep() to change
    the sampling time."""
    connected = False
    reconnecting = False
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
    """Takes ret values from PLC comm.Read and dataFileName to write time and data values to the individual csv files"""
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
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scrollWidget = QtWidgets.QWidget()
        scrollLayout = QtWidgets.QGridLayout(scrollWidget)
        scroll.setWidget(scrollWidget)
        layout.addWidget(
            scroll,
            0,
            0
        )
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
            scrollLayout.addWidget(
                group,
                row,
                0
            )
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
        layout.addWidget(
            buttons,
            1,
            0
        )
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


class ConnectedDialog(QtWidgets.QDialog):
    def __init__(self, plcName, ipAddress, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PLC Connected")
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(f"Connected to:\n{plcName}\n{ipAddress}"),
            0,
            0,
            1,
            2
        )
        self.workspaceLink = QtWidgets.QLabel(
            '<a href="#">📂 Open Workspace...</a>'
        )
        self.openWorkspace = False
        self.workspaceLink.linkActivated.connect(
            self.workspaceClicked
        )
        self.workspaceLink.setOpenExternalLinks(False)
        self.addTagLink = QtWidgets.QLabel(
            '<a href="#">🏷️ Add PLC Tag...</a>'
        )
        self.addTag = False
        self.addTagLink.linkActivated.connect(
            self.addTagClicked
        )
        self.addTagLink.setOpenExternalLinks(False)
        layout.addWidget(
            self.workspaceLink,
            1,
            0,
            1,
            2
        )
        layout.addWidget(
            self.addTagLink,
            2,
            0,
            1,
            2
        )
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(
            buttons,
            3,
            0,
            1,
            2
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
    def workspaceClicked(self):
        self.openWorkspace = True
        self.accept()
    def addTagClicked(self):
        self.addTag = True
        self.accept()


class AddTagDialog(QtWidgets.QDialog):
    def __init__(self, mainWindow):
        super().__init__(mainWindow)
        self.setWindowTitle("Add PLC Tag")
        self.resize(700, 500)
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(QtWidgets.QLabel("PLC Tag"), 0, 0)
        self.tagEdit = QtWidgets.QLineEdit()
        layout.addWidget(self.tagEdit, 0, 1)
        hint = QtWidgets.QLabel(
            "Controller: TagName\n"
            "Program Local: Program:ProgramName.TagName"
        )
        hint.setStyleSheet(
            "color: gray; font-size: 9pt;"
        )
        layout.addWidget(
            hint,
            1,
            0,
            1,
            2
        )
        layout.addWidget(
            QtWidgets.QLabel("Search Results"),
            2,
            0,
            1,
            2
        )
        self.resultList = QtWidgets.QTreeWidget()
        self.selectedTags = set()
        self.resultList.setColumnCount(2)
        self.resultList.setHeaderLabels(
            ["Tag", "Type"]
        )
        self.resultList.setRootIsDecorated(False)
        self.resultList.setAlternatingRowColors(True)
        self.resultList.setUniformRowHeights(True)
        self.resultList.setMinimumHeight(180)
        header = self.resultList.header()
        header.setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(
            self.resultList, 3, 0, 1, 2)
        self.tagEdit.textChanged.connect(
            self.filterTagList
        )
        layout.addWidget(QtWidgets.QLabel("Axis"), 4, 0)
        self.axisCombo = QtWidgets.QComboBox()
    # Populate the axis list
        self.axisCombo.addItem("Auto", None)
        for axis in range(len(mainWindow.axisViews)):
            self.axisCombo.addItem(
                mainWindow.axisName(axis),
                axis
            )
        layout.addWidget(self.axisCombo, 4, 1)
        self.buttons = QtWidgets.QDialogButtonBox()
        self.addButton = self.buttons.addButton(
            "Add Selected",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.cancelButton = self.buttons.addButton(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.addButton.clicked.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons, 5, 0, 1, 2)
        self.statusLabel = QtWidgets.QLabel()
        self.statusLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.statusLabel.setStyleSheet("""
            color: #C06000;
            font-weight: bold;
            padding: 4px;
        """)
        layout.addWidget(self.statusLabel, 6, 0, 1, 2)
        self.tagEdit.setFocus()
        if mainWindow.tagDatabaseReady():
            self.statusLabel.hide()
            self.addButton.setEnabled(True)
        else:
            self.statusLabel.setText(
                "⌛ Loading PLC Tag Database...\n"
                "You can type the tag now. OK will enable automatically."
            )
            self.addButton.setEnabled(False)
    # Put the keyboard cursor in the PLC Tag box
        self.tagEdit.setFocus()
        self.populateTagList()
        self.resultList.itemDoubleClicked.connect(
            self.resultDoubleClicked
        )
        self.resultList.itemChanged.connect(
            self.tagChecked
        )
    def populateTagList(self):
        self.resultList.clear()
        mainWindow = self.parent()
        if mainWindow.tagList is None:
            return
        for tag in sorted(
            mainWindow.tagList,
            key=lambda t: t.TagName.lower()
        ):
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, tag.TagName)
            item.setText(1, tag.DataType)
            item.setFlags(
                item.flags() |
                QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                0,
                QtCore.Qt.CheckState.Checked
                if tag.TagName in self.selectedTags
                else QtCore.Qt.CheckState.Unchecked
            )
            self.resultList.addTopLevelItem(item)
        self.updateAddButton()
    def filterTagList(self):
        text = self.tagEdit.text().strip().lower()
        root = self.resultList.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            tag = item.text(0).lower()
            dtype = item.text(1).lower()
            visible = (
                text == "" or
                text in tag or
                text in dtype
            )
            item.setHidden(not visible)
        firstVisible = None
        for i in range(root.childCount()):
            item = root.child(i)
            if not item.isHidden():
                firstVisible = item
                break
        if firstVisible is not None:
            self.resultList.setCurrentItem(firstVisible)
    def tagChecked(self, item, column):
        tag = item.text(0)
        if item.checkState(0) == QtCore.Qt.CheckState.Checked:
            self.selectedTags.add(tag)
        else:
            self.selectedTags.discard(tag)
        self.updateAddButton()
    def updateAddButton(self):
        count = len(self.selectedTags)
        self.addButton.setText(
            f"Add Selected ({count})"
        )
        self.addButton.setEnabled(
            count > 0 and
            self.parent().tagDatabaseReady()
        )
    def resultDoubleClicked(self, item, column):
        self.tagEdit.setText(item.text(0))
        self.accept()
    def databaseReady(self):
        self.populateTagList()
        self.filterTagList()
        self.statusLabel.hide()
        self.updateAddButton()


class UDTBrowserDialog(QtWidgets.QDialog):
    def __init__(self, tagName, fields, parent=None, array=False):
        super().__init__(parent)
        self.setWindowTitle("Select UDT Members")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(
                f"<b>{tagName}</b>"
            )
        )
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(
            ["Member", "Type"]
        )
        self.tree.header().setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.tree.header().setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(
            self.memberDoubleClicked
        )
        buttons = QtWidgets.QDialogButtonBox()
        self.addButton = buttons.addButton(
            "Add Selected",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.addButton.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.fields = fields
        self.array = array
        self.populate()
    def populate(self):
        self.tree.clear()
        if self.array:
            count = len(self.fields)
            for index in range(count):
                parent = QtWidgets.QTreeWidgetItem()
                parent.setText(
                    0,
                    f"[{index}]"
                )
                self.tree.addTopLevelItem(parent)
                for bit in range(16):
                    self.addChildItem(
                        parent,
                        str(bit),
                        "BOOL"
                    )
        else:
            fields = sorted(
                self.fields,
                key=lambda f: f.TagName.lower()
            )
            for field in fields:
                item = QtWidgets.QTreeWidgetItem()
                item.setText(0, field.TagName)
                item.setText(1, str(field.DataType))
                item.setFlags(
                    item.flags() |
                    QtCore.Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Unchecked
                )
                self.tree.addTopLevelItem(item)
        self.tree.expandAll()
    def selectedMembers(self):
        members = []
        def walk(item, path=""):
            name = item.text(0)
            if name.startswith("["):
                current = f"{path}{name}"
            elif path:
                current = f"{path}.{name}"
            else:
                current = name
            if item.childCount() == 0:
                if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                    members.append(current)
            else:
                for i in range(item.childCount()):
                    walk(item.child(i), current)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            walk(root.child(i))
        return members
    def addChildItem(self, parent, name, dataType):
        child = QtWidgets.QTreeWidgetItem()
        child.setText(0, name)
        child.setText(1, str(dataType))
        child.setFlags(
            child.flags() |
            QtCore.Qt.ItemFlag.ItemIsUserCheckable
        )
        child.setCheckState(
            0,
            QtCore.Qt.CheckState.Unchecked
        )
        parent.addChild(child)
    def memberDoubleClicked(self, item, column):
    # Only allow adding leaf nodes
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
            return
        item.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked
        )
        self.accept()


class ArrayBrowserDialog(QtWidgets.QDialog):
    def __init__(self, tagName, dataType, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Array Elements")
        self.resize(450, 450)
        self.tagName = tagName
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(f"<b>{tagName}</b>"))
        layout.addWidget(QtWidgets.QLabel(f"Data Type: {dataType}"))
        countLayout = QtWidgets.QHBoxLayout()
        countLayout.addWidget(QtWidgets.QLabel("Array Size:"))
        self.countSpin = QtWidgets.QSpinBox()
        self.countSpin.setRange(1, 1000)
        self.countSpin.setValue(10)
        countLayout.addWidget(self.countSpin)
        layout.addLayout(countLayout)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Element", "Type"])
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table)
        buttons = QtWidgets.QDialogButtonBox()
        self.addButton = buttons.addButton(
            "Add Selected",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.addButton.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.dataType = dataType
        self.countSpin.valueChanged.connect(self.populate)
        self.populate()
    def populate(self):
        count = self.countSpin.value()
        self.table.setRowCount(count)
        for row in range(count):
            item = QtWidgets.QTableWidgetItem(
                f"{self.tagName}[{row}]"
            )
            item.setFlags(
                item.flags() |
                QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, item)
            self.table.setItem(
                row, 1,
                QtWidgets.QTableWidgetItem(str(self.dataType))
            )
    def selectedElements(self):
        elements = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                elements.append(item.text())
        return elements


class StartupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PLC Trend Studio")
        layout = QtWidgets.QVBoxLayout(self)
        self.liveButton = QtWidgets.QRadioButton(
            "Connect to PLC"
        )
        self.historyButton = QtWidgets.QRadioButton(
            "Load Historical Data"
        )
        self.liveButton.setChecked(True)
        layout.addWidget(self.liveButton)
        layout.addWidget(self.historyButton)
    # PLC Address
        ipLayout = QtWidgets.QHBoxLayout()
        ipLayout.addWidget(
            QtWidgets.QLabel("PLC Address:")
        )
        settings = ui.loadSettings()
        self.ipEdit = QtWidgets.QComboBox()
        self.ipEdit.setEditable(True)
        self.ipEdit.setInsertPolicy(
            QtWidgets.QComboBox.InsertPolicy.NoInsert
        )
        recent = settings.get("recentPLCs", [])
        for plc in recent:
            self.ipEdit.addItem(
                f'{plc["name"]}    ({plc["ip"]})',
                plc["ip"]
            )
        self.ipEdit.setCurrentIndex(-1)
        self.ipEdit.clearEditText()
        ipLayout.addWidget(self.ipEdit)
        layout.addLayout(ipLayout)
    # Enable the PLC Address only for Live mode
        self.liveButton.toggled.connect(
            self.updateMode
        )
        self.updateMode()
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def selectedMode(self):
        if self.liveButton.isChecked():
            return "LIVE"
        return "HISTORY"
    def updateMode(self):
        self.ipEdit.setEnabled(
            self.liveButton.isChecked()
        )
    def ipAddress(self):
        text = self.ipEdit.lineEdit().text().strip()
        for index in range(self.ipEdit.count()):
            if text == self.ipEdit.itemText(index):
                return self.ipEdit.itemData(index)
        return text


class ManagePLCsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage PLCs")
        self.resize(500, 300)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(
            ["Friendly Name", "IP Address"]
        )
    # Make the table read-only
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.table)
        self.table.itemDoubleClicked.connect(
            self.memberDoubleClicked
        )
        self.renameButton = QtWidgets.QPushButton("Rename")
        self.deleteButton = QtWidgets.QPushButton("Delete")
        closeButton = QtWidgets.QPushButton("Close")
        self.renameButton.clicked.connect(
            self.renamePLC
        )
        self.deleteButton.clicked.connect(
            self.deletePLC
        )
        closeButton.clicked.connect(self.accept)
        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(self.renameButton)
        buttonLayout.addWidget(self.deleteButton)
        buttonLayout.addStretch()
        buttonLayout.addWidget(closeButton)
        layout.addLayout(buttonLayout)
    # Load saved PLCs
        settings = ui.loadSettings()
        recent = settings.get("recentPLCs", [])
        self.table.setRowCount(len(recent))
        for row, plc in enumerate(recent):
            self.table.setItem(
                row,
                0,
                QtWidgets.QTableWidgetItem(plc["name"])
            )
            self.table.setItem(
                row,
                1,
                QtWidgets.QTableWidgetItem(plc["ip"])
            )
        self.table.resizeColumnsToContents()
    def renamePLC(self):
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(
                self,
                "Rename PLC",
                "Please select a PLC first."
            )
            return
        settings = ui.loadSettings()
        recent = settings.get("recentPLCs", [])
        currentName = recent[row]["name"]
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename PLC",
            "Friendly Name:",
            text=currentName
        )
        if not ok or not name.strip():
            return
        recent[row]["name"] = name.strip()
        settings["recentPLCs"] = recent
        ui.saveSettings(settings)
        self.table.item(row, 0).setText(name.strip())
    def deletePLC(self):
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(
                self,
                "Delete PLC",
                "Please select a PLC first."
            )
            return
        settings = ui.loadSettings()
        recent = settings.get("recentPLCs", [])
        plc = recent[row]
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete PLC",
            f"Delete\n\n{plc['name']}\n({plc['ip']})?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        recent.pop(row)
        settings["recentPLCs"] = recent
    # Update lastIP if needed
        if settings.get("lastIP") == plc["ip"]:
            if recent:
                settings["lastIP"] = recent[0]["ip"]
            else:
                settings["lastIP"] = ""
        ui.saveSettings(settings)
        self.table.removeRow(row)
    def memberDoubleClicked(self, item):
        self.renamePLC()


class TagDatabaseLoader(QtCore.QThread):
    finished = QtCore.pyqtSignal(object, object)
    error = QtCore.pyqtSignal(str)
    def __init__(self, ipAddress):
        super().__init__()
        self.ipAddress = ipAddress
    def run(self):
        try:
            with PLC() as comm:
                comm.IPAddress = self.ipAddress

                comm.GetTagList()

                self.finished.emit(
                    comm.TagList,
                    comm.UDT
                )
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dataFileName, nameOfTag, ipAddress, commandQueue, liveQueue, plcProcess):
        super(MainWindow, self).__init__()
        self.connectionState = "Connecting"
        settings = ui.loadSettings()
        self.sampleInterval = settings.get(
            "sampleInterval",
            20
        )
        self.memoryMinutes = settings.get(
            "memoryMinutes",
            30
        )
        self.displayInterval = settings.get(
            "displayInterval",
            500
        )
        self.commandQueue = commandQueue
        self.liveQueue = liveQueue
        self.plcProcess = plcProcess
        self.historyMode = False
        self.workspaceLoaded = False
        self.loadingWorkspace = False
        self.tagList = None
        self.udtList = None
        self.arrayCache = {}
        self.tagLoader = None
        self.addTagDialog = None
        self.historyLoaded = False
        self.graphDirty = True
        self.historyDirty = True
        self.cursorActive = False
        self.nameOfTag = nameOfTag
        self.dataFileName = dataFileName
    # Remember PLC IP
        self.ipAddress = ipAddress
    # Every recording session gets one unique ID
        self.sessionID = datetime.datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        self.sessionFile = os.path.join(
            DATA_PATH,
            self.ipAddress.replace(".", "_"),
            f"{self.sessionID}.pts"
        )
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
        self.loadWorkspaceAction = QtGui.QAction(
            "Load Workspace...",
            self
        )
        self.saveWorkspaceAction = QtGui.QAction(
            "Save Workspace",
            self
        )
        self.saveWorkspaceAsAction = QtGui.QAction(
            "Save Workspace As...",
            self
        )
        self.loadHistoricalAction = QtGui.QAction(
            "Load Historical Data...",
            self
        )
        self.saveSnapshotAction = QtGui.QAction(
            "Save Snapshot...",
            self
        )
        fileMenu.addAction(self.loadWorkspaceAction)
        fileMenu.addAction(self.saveWorkspaceAction)
        fileMenu.addAction(self.saveWorkspaceAsAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.loadHistoricalAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.saveSnapshotAction)
        fileMenu.addSeparator()
        exitAction = QtGui.QAction(
            "Exit",
            self
        )
        fileMenu.addAction(exitAction)
        exitAction.triggered.connect(
            self.close
        )
        self.loadWorkspaceAction.triggered.connect(
            lambda checked: self.loadWorkspace()
        )
        self.saveWorkspaceAction.triggered.connect(
            lambda checked: self.saveWorkspace()
        )
        self.loadHistoricalAction.triggered.connect(
            self.loadHistoricalData
        )
        self.saveWorkspaceAsAction.triggered.connect(
            lambda checked: self.saveWorkspaceAs()
        )
        self.saveSnapshotAction.triggered.connect(
            self.saveSnapshot
        )
    # Settings Menu
        settingsMenu = menubar.addMenu("Settings")
        axisScaling = QtGui.QAction("Axis Scaling...", self)
        settingsMenu.addAction(axisScaling)
        axisScaling.triggered.connect(self.showAxisScaling)
        self.dataCollectionAction = QtGui.QAction(
            "Data Collection...",
            self
        )
        settingsMenu.addAction(
            self.dataCollectionAction
        )
        settingsMenu.addSeparator()
        managePLCs = QtGui.QAction(
            "Manage PLCs...",
            self
        )
        settingsMenu.addAction(managePLCs)
        managePLCs.triggered.connect(
            self.managePLCs
        )
        self.dataCollectionAction.triggered.connect(
            self.showDataCollection
        )
    # Add PLC Tag
        self.addTagAction = QtGui.QAction("Add PLC Tag...", self)
        settingsMenu.addSeparator()
        settingsMenu.addAction(self.addTagAction)
        self.addTagAction.triggered.connect(self.addPLCTag)
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
        self.timeWindowGroup = QtGui.QActionGroup(self)
        self.timeWindowGroup.setExclusive(True)
        sec30 = timeMenu.addAction("30 Seconds")
        min1 = timeMenu.addAction("1 Minute")
        min2 = timeMenu.addAction("2 Minutes")
        min5 = timeMenu.addAction("5 Minutes")
        min10 = timeMenu.addAction("10 Minutes")
        min15 = timeMenu.addAction("15 Minutes")
        min20 = timeMenu.addAction("20 Minutes")
        min30 = timeMenu.addAction("30 Minutes")
        hr1 = timeMenu.addAction("1 Hour")
        for action in (
            sec30,
            min1,
            min2,
            min5,
            min10,
            min15,
            min20,
            min30,
            hr1
        ):
            action.setCheckable(True)
            self.timeWindowGroup.addAction(action)
        sec30.triggered.connect(lambda: self.setTimeWindow(30))
        min1.triggered.connect(lambda: self.setTimeWindow(60))
        min2.triggered.connect(lambda: self.setTimeWindow(120))
        min5.triggered.connect(lambda: self.setTimeWindow(300))
        min10.triggered.connect(lambda: self.setTimeWindow(600))
        min15.triggered.connect(lambda: self.setTimeWindow(900))
        min20.triggered.connect(lambda: self.setTimeWindow(1200))
        min30.triggered.connect(lambda: self.setTimeWindow(1800))
        hr1.triggered.connect(lambda: self.setTimeWindow(3600))
        self.timeWindowActions = {
            30: sec30,
            60: min1,
            120: min2,
            300: min5,
            600: min10,
            900: min15,
            1200: min20,
            1800: min30,
            3600: hr1,
        }
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
        self.axisViews = [
            self.leftView,
            self.rightView,
        ]
        self.axisItems = [
            self.plotitem.getAxis("left"),
            self.plotitem.getAxis("right")
        ]
        self.axisAuto = [True, True, True]
    # Time Window (seconds)
        self.timeWindow = 300      # 5 minutes
        self.timeWindowActions[self.timeWindow].setChecked(True)
        self.updatingRange = False
    # Auto-scroll enabled
        self.autoScroll = True
        self.axisMin  = [0, 0, 0]
        self.axisMax  = [100, 100, 100]
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
        if self.ipAddress:
            self.startTagDatabaseDownload()
        self.setStyleSheet("""
        QMainWindow {
            background-color: #E3E7EB;
        }
        QMenuBar {
            background-color: #C9D3DD;
            border-bottom: 1px solid #A8B4C0;
        }
        QMenuBar::item {
            background: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background-color: #7FA8D6;
            color: black;
        }
        QMenu {
            background-color: white;
        }
        QMenu::item:selected {
            background-color: #7FA8D6;
        }
        QStatusBar {
            background-color: #C9D3DD;
            border-top: 1px solid #A8B4C0;
        }
        QDockWidget::title {
            background-color: #C9D3DD;
            padding-left: 6px;
            border-bottom: 1px solid #A8B4C0;
        }
        """)


    def tagDatabaseReady(self):
        return (
            self.tagList is not None and
            self.udtList is not None
        )


    def createCurve(self, tagName, fileName, axis):
    # Create the curve
        curve = pg.PlotDataItem(
            [],
            [],
            name=tagName
        )
        curve.setSkipFiniteCheck(True)
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
            ax.setPen("orange")
            ax.setTextPen("orange")
        else:
            ax.setPen("green")
            ax.setTextPen("green")
        self.plotitem.layout.addItem(ax, 2, column)
        self.plotitem.scene().addItem(vb)
        ax.linkToView(vb)
        vb.setXLink(self.leftView)
    # Initialize immediately
        vb.setGeometry(self.leftView.sceneBoundingRect())
        vb.linkedViewChanged(
            self.leftView,
            vb.XAxis
        )
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
        if self.liveQueue is not None:
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
        self.historyDirty = False


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
            if not self.historyMode:
                self.saveSession()
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
        if self.commandQueue is not None:
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
        if seconds in self.timeWindowActions:
            self.timeWindowActions[seconds].setChecked(True)


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
        self.graphDirty = True

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
        if self.loadingWorkspace:
            return
        if filename is None:
            filename = self.workspaceFile
        if not self.workspaceLoaded:
            return
        if not filename:
            return
        workspace = {
            "application": "PLC Trend Studio",
            "version": "8.1",
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


    def saveSession(self):
        session = {
            "application": "PLC Trend Studio",
            "version": "8.1",
            "sessionID": self.sessionID,
            "created": datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "ipAddress": self.ipAddress,
            "axes": [],
            "traces": []
        }
    # Save axis settings
        for i in range(len(self.axisViews)):
            session["axes"].append({
                "auto": self.axisAuto[i],
                "min": self.axisMin[i],
                "max": self.axisMax[i]
            })
        for c in self.curves:
            session["traces"].append({
                "tag": c["tag"],
                "displayName": c["displayName"],
                "axis": c["axis"],
                "style": c["style"].value,
                "decimals": c["decimals"],
                "visible": c["visible"]
            })
        with open(self.sessionFile, "w") as f:
            json.dump(
                session,
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
        self.workspaceLoaded = True
        self.saveWorkspace(filename)


    def loadHistoricalData(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Historical Session",
            DATA_PATH,
            "PLC Trend Studio Sessions (*.pts);;CSV Files (*.csv)"
        )
        if not filename:
            return
        folder = os.path.dirname(filename)
        extension = os.path.splitext(filename)[1].lower()
        if extension == ".pts":
            sessionFile = filename
    # User selected the session file
            with open(filename, "r") as f:
                sessionInfo = json.load(f)
            session = sessionInfo["sessionID"]
        else:
    # User selected a CSV
            base = os.path.basename(filename)
            session = base.rsplit("_", 1)[1].replace(".csv", "")
            sessionFile = os.path.join(
                folder,
                f"{session}.pts"
            )
            if os.path.exists(sessionFile):
                with open(sessionFile, "r") as f:
                    sessionInfo = json.load(f)
            else:
                sessionInfo = None
        sessionFiles = []
        for file in os.listdir(folder):
            if file.endswith(f"{session}.csv"):
                sessionFiles.append(
                    os.path.join(folder, file)
                )
        reply = QtWidgets.QMessageBox.question(
            self,
            "Historical Session",
            f"Found {len(sessionFiles)} tags from this session.\n\n"
            "Load the entire session?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.No:
            sessionFiles = [filename]
        historicalTraces = []
        if sessionInfo is not None:
    # Use the saved session information
            for trace in sessionInfo["traces"]:
                csvFile = os.path.join(
                    folder,
                    f'{trace["tag"]}_{session}.csv'
                )
                if os.path.exists(csvFile):
                    historicalTraces.append({
                        "tag": trace["tag"],
                        "displayName": trace["displayName"],
                        "axis": trace["axis"],
                        "style": trace["style"],
                        "decimals": trace["decimals"],
                        "visible": trace["visible"],
                        "file": csvFile
                    })
        else:
    # Fall back to the old behavior
            for file in sessionFiles:
                base = os.path.basename(file)
                tag = base.rsplit("_", 1)[0]
                historicalTraces.append({
                    "tag": tag,
                    "displayName": tag,
                    "axis": None,
                    "style": QtCore.Qt.PenStyle.SolidLine.value,
                    "decimals": -1,
                    "visible": True,
                    "file": file
                })
        self.openHistoricalSession(
            historicalTraces,
            sessionInfo
        )


    def managePLCs(self):
        dlg = ManagePLCsDialog(self)
        dlg.exec()


    def openHistoricalSession(
        self,
        historicalTraces,
        sessionInfo
    ):
    # Switch to Historical Mode
        self.historyMode = True
        self.graphWidget.setStyleSheet("""
            border: 2px solid #7A5A32;
        """)
        self.connectionState = "Historical Data"
        self.autoScroll = False
        self.dataCollectionAction.setEnabled(False)
        self.loadWorkspaceAction.setEnabled(False)
        self.saveWorkspaceAction.setEnabled(False)
        self.saveWorkspaceAsAction.setEnabled(False)
        self.setWindowTitle(
            "PLC Trend Studio V8 - Historical"
        )
    # Clear the current graph
        self.clearGraph()
        self.historyCache.clear()
        self.nameOfTag = []
        self.dataFileName = []
        self.axisAssignment = []
    # Build the session
        for trace in historicalTraces:
            tag = trace["tag"]
            file = trace["file"]
            data = pd.read_csv(
                file,
                engine="c"
            )
            data = np.array(data)
            self.historyCache[tag] = {
                "time": data[:,0],
                "value": data[:,1]
            }
            self.nameOfTag.append(tag)
            self.dataFileName.append(file)
            axis = trace["axis"]
    # Older sessions may not contain axis information
            if axis is None:
                axis = self.firstAvailableAxis()
            self.axisAssignment.append(axis)
            self.ensureAxisExists(axis)
            self.createCurve(
                tag,
                file,
                axis
            )
    # Restore saved properties
            curve = self.curves[-1]
            curve["displayName"] = trace["displayName"]
            curve["item"].setText(
                2,
                trace["displayName"]
            )
            curve["style"] = QtCore.Qt.PenStyle(
                trace["style"]
            )
            curve["decimals"] = trace["decimals"]
            if not trace["visible"]:
                self.toggleCurve(
                    len(self.curves)-1
                )
    # Finalize
        self.recolorCurves()
        self.updateViews()
    # Restore axis settings
        if sessionInfo is not None and "axes" in sessionInfo:
            for i, axis in enumerate(sessionInfo["axes"]):
                if i >= len(self.axisViews):
                    break
                self.axisAuto[i] = axis["auto"]
                self.axisMin[i] = axis["min"]
                self.axisMax[i] = axis["max"]
        self.applyAxisScaling()
        self.historyLoaded = True
        self.historyDirty = True
        self.graphDirty = True
        self.updateStatusBar()
    # Zoom to the loaded historical data
        if historicalTraces:
            firstTag = historicalTraces[0]["tag"]
            times = self.historyCache[firstTag]["time"]
            if len(times):
                self.leftView.setXRange(
                    times[0],
                    times[-1],
                    padding=0
                )
        self.update()


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


    def clearSession(self):
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


    def clearGraph(self):
    # Remove curves from the graph
        for c in self.curves:
            self.axisViews[c["axis"]].removeItem(
                c["curve"]
            )
    # Clear the Trace Manager
        self.traceTree.clear()
    # Clear graph objects only
        self.curves.clear()
        self.graphs.clear()
        self.axisAssignment.clear()


    def loadWorkspace(self):
        self.loadingWorkspace = True
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Workspace",
            os.path.dirname(self.workspaceFile),
            "Workspace (*.json)"
        )
        if not filename:
            self.loadingWorkspace = False
            return
        self.workspaceFile = filename
        with open(filename, "r") as f:
            workspace = json.load(f)
        while self.curves:
            self.clearSession()    
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
        self.loadingWorkspace = False
        self.workspaceLoaded = True


    def closeEvent(self, event):
        if not self.historyMode:
            self.saveWorkspace()
        if self.plcProcess is not None:
            self.plcProcess.terminate()
            self.plcProcess.join(2)
        super().closeEvent(event)


    def updateStatusBar(self):
        if self.historyMode:
            self.statusConnection.setText(
                "Source: Historical Data"
            )
        else:
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


    def startTagDatabaseDownload(self):
        if self.tagLoader is not None:
            return
        self.statusBar.showMessage(
            "Downloading PLC Tag Database..."
        )
        self.tagLoader = TagDatabaseLoader(
            self.ipAddress
        )
        self.tagLoader.finished.connect(
            self.tagDatabaseLoaded
        )
        self.tagLoader.error.connect(
            self.tagDatabaseError
        )
        self.tagLoader.start()


    def tagDatabaseLoaded(self, tagList, udtList):
        self.tagList = tagList
        self.udtList = udtList
        self.statusBar.showMessage(
            f"Loaded {len(tagList)} tags and {len(udtList)} UDTs.",
            5000
        )
        self.tagLoader = None
        if self.addTagDialog is not None:
            self.addTagDialog.databaseReady()


    def tagDatabaseError(self, message):
        self.tagLoader = None
        QtWidgets.QMessageBox.warning(
            self,
            "Tag Database",
            f"Unable to download the PLC tag database.\n\n{message}"
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
            tagName,
            self.sessionID
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
        self.saveSession()
        self.workspaceLoaded = True
        return len(self.curves)-1


    def findArrayLength(self, tagName):
        low = 0
        high = 1
        with PLC() as comm:
            comm.IPAddress = self.ipAddress
            while True:
                ret = comm.Read(f"{tagName}[{high}]")
                if ret.Status == "Success":
                    low = high
                    high *= 2
                    if high > 100000:
                        return high
                else:
                    break
            while low + 1 < high:
                mid = (low + high) // 2
                ret = comm.Read(f"{tagName}[{mid}]")
                if ret.Status == "Success":
                    low = mid
                else:
                    high = mid
            return low + 1


    def addPLCTag(self):
        self.addTagDialog = AddTagDialog(self)
        dlg = self.addTagDialog
        try:
            if not dlg.exec():
                return
            axis = dlg.axisCombo.currentData()
            if dlg.selectedTags:
                for tag in sorted(dlg.selectedTags):
                    self.addSingleTag(
                        tag,
                        axis
                    )
            else:
                tag = dlg.tagEdit.text().strip()
                if tag:
                    self.addSingleTag(
                        tag,
                        axis
                    )
        finally:
            self.addTagDialog = None


    def addSingleTag(self, tagName, axis):
        if self.tagLoader is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Loading PLC Tags",
                "PLC tags are still loading in the background.\n\n"
                "Please try again in a few seconds."
            )
            return
        if tagName in self.nameOfTag:
            QtWidgets.QMessageBox.information(
                self,
                "Already Exists",
                f"{tagName} is already being trended."
            )
            return
        # Direct tag (member, indexed tag, bit, etc.)
        if "." in tagName or ("[" in tagName and "]" in tagName):
            with PLC() as comm:
                comm.IPAddress = self.ipAddress
                ret = comm.Read(tagName)
            if ret.Status != "Success":
                QtWidgets.QMessageBox.warning(
                    self,
                    "Tag Not Found",
                    f"'{tagName}' could not be read.\n\n"
                    f"PLC returned:\n{ret.Status}"
                )
                return
            self.addTag(
                tagName,
                axis=axis
            )
            return
        if self.tagList is None or self.udtList is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Tag Database",
                "The PLC tag database is not available."
            )
            return
        # Find the tag
        tagInfo = None
        for t in self.tagList:
            if t.TagName == tagName:
                tagInfo = t
                break
        if tagInfo is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Tag Not Found",
                f"'{tagName}' was not found in the PLC."
            )
            return
        # UDT
        if tagInfo.Struct:
            udt = self.udtList.get(tagInfo.DataTypeValue)
            if udt is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "UDT Error",
                    f"Unable to locate UDT definition for\n\n{tagInfo.DataType}"
                )
                return
            browser = UDTBrowserDialog(
                tagName,
                udt.Fields,
                self
            )
            if browser.exec():
                for member in browser.selectedMembers():
                    fullTag = f"{tagName}.{member}"
                    if fullTag in self.nameOfTag:
                        continue
                    self.addTag(
                        fullTag,
                        axis=axis
                    )
            return
        # Array
        if tagInfo.Array:
            count = self.findArrayLength(tagName)
            browser = UDTBrowserDialog(
                tagName,
                list(range(count)),
                self,
                array=True
            )
            if browser.exec():
                for member in browser.selectedMembers():
                    fullTag = f"{tagName}{member}"
                    if fullTag in self.nameOfTag:
                        continue
                    with PLC() as comm:
                        comm.IPAddress = self.ipAddress
                        ret = comm.Read(fullTag)
                    if ret.Status != "Success":
                        continue
                    self.addTag(
                        fullTag,
                        axis=axis
                    )
            return
        # Normal controller tag
        with PLC() as comm:
            comm.IPAddress = self.ipAddress
            ret = comm.Read(tagName)
        if ret.Status != "Success":
            QtWidgets.QMessageBox.warning(
                self,
                "Tag Not Found",
                f"'{tagName}' could not be read.\n\n"
                f"PLC returned:\n{ret.Status}"
            )
            return
        self.addTag(
            tagName,
            axis=axis
        )

        
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
    # We are now viewing history instead of live scrolling
        self.historyMode = True
    # Change background only if this is a Live Review,
    # not a Historical Session.
        if self.connectionState != "Historical Data":
            self.graphWidget.setStyleSheet("""
            border: 2px solid #7A5A32;
        """)
        if not self.historyLoaded:
            self.loadHistory()
            self.historyLoaded = True
        self.historyDirty = True
        self.graphDirty = True
        if hasattr(self, "liveModeAction"):
            self.liveModeAction.setChecked(False)


    def toggleLiveMode(self):
        self.autoScroll = self.liveModeAction.isChecked()
        if self.autoScroll:
            self.historyMode = False
            self.graphWidget.setStyleSheet("""
                border: 2px solid #808080;
            """)
            self.connectionState = "🟢 Connected"
            self.dataCollectionAction.setEnabled(True)
            self.loadWorkspaceAction.setEnabled(True)
            self.saveWorkspaceAction.setEnabled(True)
            self.saveWorkspaceAsAction.setEnabled(True)
            self.updateStatusBar()
            self.historyCache.clear()
            self.historyLoaded = False
            self.timer.start(self.displayInterval)
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
    dataFileName = []
# Ask for a PLC until we get one
    dlg = StartupDialog()
    if not dlg.exec():
        return
    mode = dlg.selectedMode()
    if mode == "LIVE":
        while True:
            ipAddress = dlg.ipAddress()
            if not ipAddress:
                QtWidgets.QMessageBox.warning(
                    None,
                    "PLC Address Required",
                    "Please enter a PLC IP address."
                )
                return
            settings = ui.loadSettings()
            sampleInterval = settings.get(
                "sampleInterval",
                20
            )
            with PLC() as comm:
                comm.IPAddress = ipAddress
                try:
                    result = comm.GetDeviceProperties()
                except Exception:
                    result = None
            if result is not None and result.Status == "Success":
                recent = settings.get("recentPLCs", [])
    # See if this PLC already exists
                existing = None
                for plc in recent:
                    if plc["ip"] == ipAddress:
                        existing = plc
                        break
    # Ask for a friendly name if this is new
                if existing is None:
                    name, ok = QtWidgets.QInputDialog.getText(
                        None,
                        "New PLC",
                        f"Friendly name for\n\n{ipAddress}"
                    )
                    if not ok or not name.strip():
                        name = ipAddress
                    existing = {
                        "name": name.strip(),
                        "ip": ipAddress
                    }
                else:
                    recent.remove(existing)
    # Move to the top
                recent.insert(0, existing)
                settings["recentPLCs"] = recent[:10]
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
            dlg.ipEdit.setEditText(ipAddress)
            dlg.ipEdit.setFocus()
            dlg.ipEdit.lineEdit().selectAll()
            if not dlg.exec():
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
                liveQueue,
                sampleInterval
            )
        )
        p1.start()
    else:
        ipAddress = ""
        nameOfTag = []
        commandQueue = None
        liveQueue = None
        p1 = None
#    time.sleep(3)
    w = MainWindow(
        dataFileName,
        nameOfTag,
        ipAddress,
        commandQueue,
        liveQueue,
        p1
    )
    if mode == "LIVE":
        w.setWindowTitle(
            "PLC Trend Studio V8 - Live"
        )
    else:
        w.setWindowTitle(
            "PLC Trend Studio V8 - Historical"
        )
        w.loadWorkspaceAction.setEnabled(False)
        w.saveWorkspaceAction.setEnabled(False)
        w.saveWorkspaceAsAction.setEnabled(False)

        w.addTagAction.setEnabled(False)
        w.dataCollectionAction.setEnabled(False)
    w.show()
    if mode == "LIVE":
        settings = ui.loadSettings()
        plcName = ipAddress
        for plc in settings.get("recentPLCs", []):
            if plc["ip"] == ipAddress:
                plcName = plc["name"]
                break
        dlg = ConnectedDialog(
            plcName,
            ipAddress,
            w
        )
        if dlg.exec():
            if dlg.openWorkspace:
                w.loadWorkspace()
            elif dlg.addTag:
                w.addPLCTag()
    if mode == "HISTORY":
        QtCore.QTimer.singleShot(
            0,
            w.loadHistoricalData
        )
    sys.exit(app.exec())


if __name__ == '__main__':
    mp.freeze_support()
    main()
