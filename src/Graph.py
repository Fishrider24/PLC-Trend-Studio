import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.multiprocess as mp

def plotTheData(dataFileName, i):
    #if(i == 1):
    #    graph.clear()
    data = pd.read_csv(dataFileName[0])
    data = np.array(data)
    graph = pg.plot(data, title="LMaO who needs RStudio to plot", pen='r')
    axis = pg.DateAxisItem()
    graph.setAxisItems({'bottom':axis})
    if len(dataFileName) > 1:
        for i in range(1, len(dataFileName)):
            data = pd.read_csv(dataFileName[i])
            data = np.array(data)
            graph.plot(data)

if __name__ == '__main__':
    pg.exec()
