@echo off

REM Runs the Python script and passes all command-line arguments to it. In short, if this Batch file was ran from Terminal as `Run.bat <Command> --<Arguments>`, it'd be the same as running the script in said way. In lieu, if it's just executed normally, nothing will be passed, and the defaults will take over.
python Pesto.py %*

REM Keeps the window open in order for the user to see the output.
pause
