# PLC Trend Studio V6.3
PLC Trend Studio is a Windows application for real-time monitoring, trending, and troubleshooting of Allen-Bradley PLCs over Ethernet/IP.

Designed for controls engineers and maintenance technicians, it provides live trending, historical data review, unlimited configurable Y-axes, automatic CSV logging, and workspace management in a lightweight desktop application.

Features
📈 Real-time PLC tag trending
⚡ Live and History viewing modes
📊 Unlimited independently scaled Y-axes
🎨 Configurable trace colors and line styles
💾 Automatic CSV data logging
🗂 Workspace save/load
🔄 Automatic restoration of axis layouts and trace assignments
🏷 Per-PLC tag lists and workspaces
✔ Supports analog, digital, and bit-level PLC tags
🚀 Optimized in-memory buffering for responsive live trending

In Settings, you can adjust scaling for the y-axis and add new PLC tags.  On traces, you can delete tags, change line style, move to different y-axis and hide/show data for tags.

<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/setting.png" width="200">&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/trace.png" width="200">

In View, you can change the time window you are in 30secs, 1,2,5,10,30 minutes and 1 hour.  You can drag farther and it will load data from the csv files.  Currently it stores 30 minutes of data in ram.  View also have the toggle for live mode.  Workspace will save the layout (axis, scaling, tags, line format) in a file that is tied to the ip address of the PLC.  Load it in after you start your graph.

<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/views.png" width="200">&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/workspaces.png" width="200">

Release has a packaged .exe using PyInstaller.  Use that or look through the code and package yourself.

## Building

Prerequisites

- Python 3.10 or newer

Install the required packages:

```bash
pip install -r requirements.txt
```

Build the Windows executable:

```bash
pyinstaller --onefile --console PLC_TrendStudio_V6.3.py
```

PLC Trend Studio was created to provide many of the capabilities of commercial industrial trend software in a fast, easy-to-use application for everyday troubleshooting and process analysis.

PLC Trend Studio is built using the following open-source projects:

- **Python** – Programming language - [Python](https://www.python.org/)
- **PyQt6** – Graphical user interface - [PyQt6](https://pypi.org/project/PyQt6/)
- **PyQtGraph** – High-performance real-time plotting - [PyQtGraph](https://www.pyqtgraph.org/)
- **PyLogix** – Allen-Bradley Ethernet/IP communications - [PyLogix](https://github.com/dmroeder/pylogix)
- **NumPy** – Numerical data processing - [NumPy](https://numpy.org/)
- **Pandas** – CSV handling and data processing - [Pandas](https://pandas.pydata.org/)
- **PyInstaller** – PyInstaller bundles a Python application and all its dependencies into a single package. – [PyInstaller](https://github.com/pyinstaller/pyinstaller)

Special thanks to the developers and contributors of these projects for making them available to the community.

## Disclaimer

PLC Trend Studio is intended as a diagnostic and troubleshooting tool.

It is not designed or intended to perform machine control or safety-related functions. Users are responsible for validating all data and ensuring safe operation of their equipment.

This project is licensed under the MIT License. See the LICENSE file for details.
