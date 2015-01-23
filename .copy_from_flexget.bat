@echo off
copy /V /Y C:\Workspace\Flexget\flexget\plugins\local\*.py C:\Workspace\.flexget\plugins\
del C:\Workspace\.flexget\plugins\__init__.py
del C:\Workspace\.flexget\plugins\friendfeed2.py
pause