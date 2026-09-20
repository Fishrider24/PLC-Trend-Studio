# PLC Trend Studio V7.0
PLC Trend Studio is a Windows application for real-time monitoring, trending, and troubleshooting of Allen-Bradley PLCs over Ethernet/IP.

## Trademarks
Allen-Bradley, ControlLogix, CompactLogix, and Studio 5000 are trademarks of Rockwell Automation, Inc. This project is not affiliated with, sponsored by, or endorsed by Rockwell Automation.
## Overview
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

PLC Trend Studio V7 Overview

Version 7 represents the largest architectural update since the project began. The focus has shifted from adding graphing features to improving usability, reliability, and workflow.

New Features

Workspace-Based Configuration
Save and load complete workspaces.

Workspaces now store trace configuration including:

PLC tags

Display names

Axis assignments

Line styles

Decimal display settings

Visibility

Axis scaling

Save Workspace As, 
Create multiple named workspaces for different machines or troubleshooting sessions.

Custom Display Names
Assign user-friendly names to traces while preserving the original PLC tag.
Hovering over a trace displays the actual PLC tag name.

Per-Trace Decimal Formatting
Individual traces can display different decimal precision.
Added Auto formatting to intelligently remove unnecessary trailing zeros.

Per-Trace Line Styles
Solid
Dashed
Dotted
Dash-Dot

Enhanced Trace Manager, 
Added Style column.
Added color indicators.

Right-click menu now manages:

Axis assignment

Line style

Decimal precision

Display name

Hide/Show

Remove tag

Interactive Cursor, 
Hold Ctrl to enable a vertical cursor.
Displays trace values at the selected timestamp.
Works in both Live and History modes.

Communication Improvements
Automatic PLC connection verification during startup.
User is prompted to re-enter an IP address if the PLC cannot be reached.
Automatic reconnect after communication loss.
Communication interruptions create visible gaps in the trend instead of connecting data across outages.
PLC connection status is shown in the application status bar.

Reliability Improvements
Invalid PLC tags are detected before being added.
REAL arrays and floating-point values (including negative values) are fully supported.
Live and historical Boolean values are now consistently displayed as 0 and 1.
Improved startup with an empty graph and dynamic tag loading.

User Interface Improvements
Cleaner startup workflow.
Graph starts with only Left and Right 1 axes.
Additional axes are created automatically as needed.

Improved Trace Manager layout.
Numerous performance and code cleanup improvements.

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
pyinstaller --onefile --console PLC_Trend_StudioV7.0.py
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
