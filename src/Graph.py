import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.multiprocess as mp

#data = pd.read_csv('BellyRoll_TACH_Filtered_Aug08145117.csv')
#data = np.array(data)
#data2 = pd.read_csv('BellyRoll_Tach_Raw_Aug08145120.csv')
#data2 = np.array(data2)
###dataAxis = data[:,1]
###data = data[:,0]
###data = np.array(data, dtype=float)
###data = np.random.normal(size=1000)

#graph = pg.plot(data, title="LMaO who needs RStudio to plot", pen='r')
#graph.plot(data2, pen='b')
#axis = pg.DateAxisItem()
#graph.setAxisItems({'bottom':axis})


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

    #pg.exec()




#dataFileName =['BellyRoll_TACH_Filtered_Aug08145117.csv']
#plotTheData(dataFileName)



if __name__ == '__main__':
    pg.exec()
