# nmea_seatalk_multiplexer
Python-Multiplexer for NMEA and Seatalk-Devices (via Serial, TCP, File...)


# Why
I tried to work with [marnav](https://github.com/mariokonrad/marnav/)'s library. It is a huge and good project. But it seemed too complicated and over the top for me:

* Written in C++ 
* Many dependencies 
* Only works on linux
* To set it up is complex/complicated

Why am i writing that? I don't want to run that project on a "big" computer. I wanted to get this done on a Raspberry-like system (Orange Pi zero). 
To set up a remote-debugger and cross compiler, it was a little too much just for testing.

# Features

* Runs on Windows and Linux (Tested Windows 10, Armbian)
* Python 3 (Tested Python 3.6)
* Easy logging for raw-data and "normal" logging
* Support for IO:
** TCP
** File
** Serial
* Devices are JSON-configurable (no need to directly write your devices into code)
