import time
import datetime
from pylogix import PLC
import csv
import pandas as pd
import numpy as np
import os.path
from paths import DATA_PATH, PREVIOUS_TAGS_PATH


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

def usePreviousTag(ipAddress):
    """Print list of previous tags and ask if user would like to scan them again"""
    Flag = False
    PreviousTag = os.path.join(
        PREVIOUS_TAGS_PATH,
        ipAddress.replace(".", "_") + ".csv"
    )
    if os.path.isfile(PreviousTag) == True:
        data = pd.read_csv(PreviousTag)
        data = data.columns
        data = data.tolist()
        if len(data) > 0:
            for i in range(0, len(data)):
                print(data[i])
        x = input('Use Previous Tags? ')
        if x == 'y':
            PreviousTags = data
            if len(PreviousTags) > 0:
                for i in range(0, len(PreviousTags)):
                    with PLC(ipAddress) as comm:
                        ret = comm.Read(PreviousTags[i])
                    if ret.Status == 'Success':
                        Flag = True
                    else:
                        Flag = False
                        break
            if Flag == True:
                return(PreviousTags)
            else:
                print('One Or More Tags Not Found')
                return(False)
        elif x == 'n':
            return(False)
    else:
        print('No Previous Tags Found')
        return(False)

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
    with open('PreviousTags.csv', 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(listOfTag)
    return(listOfTag)

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

def dataFeatherCreation(nameOfTag):
    """Creates the pickle files as pickle based on the tag name"""
    timestamp = time.time()
    data = [timestamp, 0]
    data = pd.DataFrame(data)
    dataFeatherName = "{}_{}.feather" .format(nameOfTag, time.strftime("%b%d%H%M%S"))
    data.to_feather(dataPickleName)
    return(dataPickleName)

def savePreviousTags(ipAddress, tagList):
    PreviousTag = os.path.join(
        PREVIOUS_TAGS_PATH,
        ipAddress.replace(".", "_") + ".csv"
    )
    df = pd.DataFrame(columns=tagList)
    df.to_csv(
        PreviousTag,
        index=False
    )
