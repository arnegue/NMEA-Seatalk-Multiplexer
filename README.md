# NMEA-Seatalk-Multiplexer
Python-Multiplexer for NMEA- and Seatalk-Devices

## Why
I tried to work with [marnav](https://github.com/mariokonrad/marnav/)'s library. It is a huge and good project. But it seemed too complicated and over the top for me:

* Written in C++ 
* Many dependencies 
* Only works on linux
* To set it up is complex/complicated

Why am i writing that? I don't want to run that project on a "big" computer. I wanted to get this done on a Raspberry-like system (Orange Pi zero). 
To set up a remote-debugger and cross compiler, it was a little too much just for testing.

## Features

* Runs on Windows and Linux (Tested Windows 10, Armbian 4.19)
* Python 3 (Tested Python 3.6)
* Easy logging for raw-data and "normal" logging
* Supported data:
  * NMEA
  * Seatalk (writing partially supported because of missing bit-toggling)
  * (I2C for NASA-Clipper-Devices to be done, [similar to openseamap](http://wiki.openseamap.org/wiki/De:NASA_Clipper_Range))
* Support for IO:
  * TCP (Client and Server, currently only one client allowed)
  * File
  * Serial
  * StdOut (only out)
* Devices are JSON-configurable (no need to directly write your devices into code)

## Invocation

Start the program with like this:

* Default devices-file: ``python -m main_file``
* Custom devices-file (in this example ``my_devices.json``): ``python -m main_file --devices my_devices.json``

## Creating your devices

Usually the default devices list is ``devices.json`` but you can also specify it with running ``python -m main_file --devices <my_file.json>``.
There is already an example-``devices.json`` in this repository.

A typical device is built like this:

```json
{
  "DeviceName": {
    "type": "io",
    "device_io": {
        ...
    },
    "observers": [
        ...
    ]
  },
}
```

* The ``DeviceName`` is up to you but must be unique and is important for the ``observers``-section
* The ``type`` specifies the type of data the devices receives (currently only ``NMEADevice`` and ``SeatalkDevice`` is supported)
* ``device_io`` sets the IO-Settings needed for communication to that device (explained below).
  * Every ``device_io`` needs at least ``type`` to ensure which I/O to be used.
  * Settings ``encoding`` os optional for every ``device_io``
  * Every other settings given in that section depend on the ``type``
* The ``observer`` section contains a list of 0-n DeviceNames which observe this device (getting this device's data)


### TCP

You can create either create a TCP-Server or a -Client

#### Server

This example creates a TCP-Server called "MyTCPServer" on port 9900 with ACII-Encoding. This device's type is NMEADevice. So it only transmits/receives NMEA-Strings.

```json
"MyTCPServer": {
  "type": "NMEADevice",
  "device_io": {
    "type": "TCPServer",
    "port": "9900",
    "encoding": "ASCII"
  },
  "observers": [
  ]
}
```
 
#### Client

This example creates a client which will try to connect to ``172.24.1.1:9901``. Setting ``ip`` to a hostname does also work.

```json
"MyTCPClient": {
  "type": "NMEADevice",
  "device_io": {
    "type": "TCPClient",
    "port": "9901",
    "ip": "172.24.1.1",
    "encoding": "ASCII"
  },
  "observers": [
  ]
}
```
 
### File

This example reads/writes from/to file located at ``/tmp/my_nmea_file.txt``.

```json
"MyFileReadWriter": {
  "type": "NMEADevice",
  "device_io": {
    "type": "File",
    "path": "/tmp/my_nmea_file.txt",
    "encoding": "ASCII"
  },
  "observers": [
  ]
}
```

### Serial

This may be the most important section.

* port - Serial-Port. Example Windows: "COM5", Unix "/dev/ttyS2"
* baudrate - default 4800
* bytesize - default 8
* stopbites - default 1
* parity - default None

Given example shows a Seatalk-Device on port ``/dev/ttyUSB3/`` with parity set to ``Mark`` without(!) encoding.
Additionally the observer "MyTCPServer" is listening to this device. 

```json
"Seatalk": {
  "type": "SeatalkDevice",
  "device_io": {
    "type": "Serial",
    "port": "/dev/ttyUSB3",
    "parity": "Mark"
  },
  "observers": [
    "MyTCPServer"
  ]
}
```


### StdOutPrinter

This devices just prints out to StdOut (StdIn currently not supported):

```json
"MyConsoleSpammer": {
  "type": "NMEADevice",
  "device_io": {
    "type": "StdOutPrinter",
    "encoding": "UTF-8"
  },
  "observers": [
  ]
}
```

## Logging

There are two different kinds of logging: RawDataLogger and GlobalLogger. Every device has a own logger-which writes received data to a logfile ``./log/<DeviceName>_raw.log``. The Global Logger writes general (debug-)info to ``./logs/main_log.log``.

### How much is logged

These logger are using RotatingFileHandler.

> Handler for logging to a set of files, which switches from one file to the next when the current file reaches a certain size.
>  -- <cite>logging.handlers.RotatingFileHandler</cite>

* Mode: append
* MaxSize per file (bytes): 5 * 1024 * 1024
* Amount of BackupFiles: 2
