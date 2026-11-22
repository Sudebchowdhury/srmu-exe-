@echo off
REM Builds a single-file Windows executable:  dist\EV-Charging-Emission-Calculator.exe
REM Requires Python 3.10+ (with Tcl/Tk, included in the python.org installer).
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name EV-Charging-Emission-Calculator ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import matplotlib.backends.backend_pdf ^
    main.py
echo.
echo Done. Your .exe is in the dist folder.
pause
