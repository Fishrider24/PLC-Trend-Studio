# PLC Trend Studio
PLC Trend Studio is a Windows desktop application for real-time monitoring, historical analysis, and troubleshooting of Allen-Bradley PLCs over EtherNet/IP. (It can also run under Python on Linux, although this configuration has not been fully tested.)
Designed for controls engineers and maintenance technicians, PLC Trend Studio provides fast live trending, historical session playback, automatic data logging, and flexible graphing tools in a lightweight desktop application.
## Trademarks
Allen-Bradley, ControlLogix, CompactLogix, Studio 5000, and EtherNet/IP are trademarks of Rockwell Automation, Inc.
PLC Trend Studio is an independent open-source project and is not affiliated with, sponsored by, or endorsed by Rockwell Automation.

Major Features
- 📈 Real-time PLC tag trending
- 🕘 Live Review Mode for scrolling back through recorded data while remaining connected
- 📂 Historical Session playback using .pts session files
- 📊 Unlimited independently scaled Y-axes
- 🏷 Display names, line styles, decimal formatting, and visibility control
- 💾 Automatic CSV data logging
- 🗂 Workspace save/load
- 📁 Historical session management
- 🖧 Friendly PLC names and PLC Manager
- ✔ Supports controller tags, program-local tags, analog values, digital values, and individual bits
- ⚡ Optimized graph rendering for responsive live trending

What's New in Version 8
Version 8 represents the largest feature expansion since PLC Trend Studio was created. The application has evolved from a live PLC trend viewer into a complete live and historical troubleshooting tool.
Major Changes
- Added Historical Session Mode with support for complete session playback using .pts session files.
- Added Live Review Mode for reviewing recorded data while remaining connected to the PLC.
- Redesigned startup workflow with Live/Historical selection, friendly PLC names, recent PLC list, and PLC Manager.
- Added Connected startup screen with quick access to Open Workspace and Add PLC Tag.
- Added unlimited right-side Y-axes with independent scaling and automatic axis restoration.
- Expanded trace management with display names, line styles, decimal formatting, visibility control, and axis reassignment.
- Added Workspace management to save and restore complete graph layouts.
- Improved Add PLC Tag with program-local tag support, automatic display names, axis selection, and live PLC validation.
- Added configurable data collection settings with persistent startup values.
- Improved graph performance, rendering stability, and live responsiveness.

Trace Management
Settings allow you to:
- Configure Y-axis scaling
- Add PLC tags
- Adjust data collection settings
The Trace Manager allows you to:
- Move traces between axes
- Change line styles
- Rename display names
- Adjust decimal precision
- Hide/Show traces
- Remove traces

<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/setting.png" width="200">&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;<img src="https://github.com/Fishrider24/PLC-Trend-Studio/blob/main/screenshots/trace.png" width="200">

View Menu
The View menu provides:
- Time windows from 30 seconds to 1 hour
- Live Review Mode
- Grid display
- Live Mode toggle
Dragging the graph automatically loads older CSV data for review while maintaining the live connection.

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
python -m PyInstaller --onefile --icon=C:\path\to\file\pts2.png --windowed PLC_Trend_StudioV8.py
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
- **Pillow (PIL)** – Image processing and screenshot support – https://python-pillow.org/

Special thanks to the developers and contributors of these projects for making them available to the community.

## Disclaimer

PLC Trend Studio is intended as a diagnostic and troubleshooting tool.

It is not designed or intended to perform machine control or safety-related functions. Users are responsible for validating all data and ensuring safe operation of their equipment.

This project is licensed under the MIT License. See the LICENSE file for details.
