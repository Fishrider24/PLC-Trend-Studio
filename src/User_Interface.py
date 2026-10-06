import time
import datetime
from pylogix import PLC
import csv
import pandas as pd
import numpy as np
import os.path
from paths import DATA_PATH
import json
from paths import SETTINGS_FILE


def splitBitTag(tag):
    """
    Converts:
        B1007[6].7
    into:
        ("B1007[6]", 7)
    Normal tags return:
        ("TagName", None)
    """
    if "." not in tag:
        return tag, None
    base, bit = tag.rsplit(".", 1)
    if bit.isdigit():
        return base, int(bit)
    return tag, None

def tagName():
    x = input('Enter Tag name: ')
    if x == 'n':
        print('done')
    return(x)

def ipName():
    x = input('Enter IP Address: ')
    return(x)

def ipDialog(parent=None, defaultIP=""):
    from PyQt6 import QtWidgets
    ip, ok = QtWidgets.QInputDialog.getText(
        parent,
        "Connect to PLC",
        "PLC IP Address:",
        text=defaultIP
    )
    if not ok:
        return None
    return ip.strip()

def loadSettings():
    settings = {
        "lastIP": "",
        "sampleInterval": 20,
        "memoryMinutes": 30,
        "displayInterval": 500
    }
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    return settings

def saveSettings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(
            settings,
            f,
            indent=4
        )

def tagCheck(ipAddress, nameOfTag):
    flag = False
    listOfTag = []
    while flag != True:
        baseTag, bit = splitBitTag(nameOfTag)
        with PLC(ipAddress) as comm:
            ret = comm.Read(baseTag)
        if ret.Status == 'Success':
            listOfTag.append(nameOfTag)
            question = input('add another tag? y or n? ')
            if question == 'y':
                nameOfTag = tagName()
            elif question == 'n':
                flag = True
        else:
            print(ret.Status)
            print('!Tag name was not found. Try Again.')
            nameOfTag = tagName()

def dataFileCreation(ipAddress, nameOfTag):
    ipFolder = ipAddress.replace(".", "_")
    folder = os.path.join(
        DATA_PATH,
        ipFolder
    )
    os.makedirs(folder, exist_ok=True)
    filename = "{}_{}.csv".format(
        nameOfTag,
        time.strftime("%b%d%H%M%S")
    )
    dataFileName = os.path.join(
        folder,
        filename
    )
    with open(dataFileName, "a", encoding="UTF8"):
        pass
    return dataFileName
