# NMEA-Seatalk-Multiplexer
Python-Multiplexer for NMEA- and Seatalk-Devices

## Why
I tried to work with [marnav](https://github.com/mariokonrad/marnav/)'s library. It is a huge and good project. But for me it seemed too complicated and over the top:

* Written in C++ 
* Many dependencies 
* Only works on linux
* To set it up is complex/complicated

Why am i writing that? I don't want to run that project on a "big" computer. I wanted to get this done on a Raspberry-like system (Orange Pi zero). 
It was a little too much just for testing to set up a remote-debugger and cross compiler.

## Features

* Runs on Windows and Linux (Tested Windows 10, Armbian 4.19, Raspbian)
* Python >=3.6
* Easy logging for raw-data and "normal" logging
* Supported interfaces:
  * NMEA
  * Seatalk (writing partially supported because of missing bit-toggling when writing to interface)
  * (I2C for NASA-Clipper-Devices to be done, [similar to openseamap](http://wiki.openseamap.org/wiki/De:NASA_Clipper_Range))
* Support for IO:
  * TCP (Client and Server, currently only one client allowed)
  * File
  * Serial
  * StdOut (only out)
* Devices are JSON-configurable (no need to directly write your devices into code)

## Invocation

Start the program like this:

* Default devices-file: ``python -m main_file``
* Custom devices-file (in this example ``my_devices.json``): ``python -m main_file --devices my_devices.json``

## Supported Interfaces

### NMEA 0183

Since this project only produces NMEA-Output every NMEA-Device is supported which produces a new line at the end. Usually no parsing (but checksum) is happening.

But some parsing/creation of NMEA-Sentences are supported:
* RMC (Recommended Minimum Sentence) 
* VHW (Speed Through Water)
* DBT (Depth Below Keel)
* MTW (Water Temperature) 
* MWV (Wind Speed and Angle)

### Seatalk 1
 
A big part of help for parsing Seatalk-Sentences and building hardware to be able to receive has come from [Thomas Knauf](http://www.thomasknauf.de/seatalk.htm).

As written above: Writing to bus is buggy right now because of missing bit-toggling
Some Seatalk-Messages do not have a corresponding NMEA-Sentence. 

#### Supported (and tested on ST50 and ST60) Seatalk-IDs:

* 0x00 - Depth below transducer
* 0x20 - Speed through water (1)
* 0x23 - Water Temperature (1)
* 0x24 - Set Display Unit for Mileage and Speed
* 0x26 - Speed through water (2)
* 0x27 - Water Temperature (2)
* 0x30 - Set Lamp Intensity (1)

#### Implemented but untested (missing Equipment) Seatalk-IDs:

* 0x01 - Equipment ID (1)
* 0x10 - Apparent Wind Angle
* 0x11 - Apparent Wind Speed
* 0x21 - Trip Mileage
* 0x22 - Total Mileage
* 0x36 - Cancel MOB
* 0x38 - CodeLock Data
* 0x52 - Speed Over Ground
* 0x55 - KeyStroke (1)
* 0x56 - Date
* 0x57 - Satellite Info
* 0x59 - Set Count Down Timer
* 0x61 - E80-Initialization
* 0x65 - Select Fathom
* 0x66 - Wind Alarm
* 0x68 - Alarm Acknowledgment Keystroke
* 0x6C - Equipment ID (2)
* 0x6E - Man Over Board
* 0x80 - Set Lamp Intensity (2)
* 0x86 - KeyStroke (2)
* 0x87 - Set Response Level
* 0x90 - Device Identification (2)
* 0x91 - Set Rudder Gain
* 0x93 - Enter AP-Setup
* 0xA4 - Device Identification (BroadCast, Termination, Answer)

(n) means there are multiple Datagrams with same/similar meaning.

### I2C

To be done: Testing on [NASA Clipper Instruments](https://www.nasamarine.com/product-category/products/instruments/clipper/)


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
  * Settings ``encoding`` is optional for every ``device_io``
  * Every other settings given in that section depend on the ``type``
* The ``observer`` section contains a list of 0-to-n DeviceNames which observe this device (getting this device's data)


### TCP

You can create either a TCP-Server or a -Client

#### Server

This example creates a TCP-Server called "MyTCPServer" on port 9900 with ASCII-Encoding. This device's type is NMEADevice. So it only transmits/receives NMEA-Strings.

```json
{
  "MyTCPServer": {
    "type": "NMEADevice",
    "device_io": {
      "type": "TCPServer",
      "port": 9900,
      "encoding": "ASCII"
    },
    "observers": [
    ]
  }
}
```
 
#### Client

This example creates a client which will try to connect to ``172.24.1.1:9901``. Setting ``ip`` to a hostname does also work.

```json
{
  "MyTCPClient": {
    "type": "NMEADevice",
    "device_io": {
      "type": "TCPClient",
      "port": 9901,
      "ip": "172.24.1.1",
      "encoding": "ASCII"
    },
    "observers": [
    ]
  }
}
```
 
### File

This example reads/writes from/to file located at ``/tmp/my_nmea_file.txt``.

```json
{
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
{ 
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
}
```


### StdOutPrinter

This devices just prints out to StdOut (StdIn currently not supported):

```json
{
  "MyConsoleSpammer": {
    "type": "NMEADevice",
    "device_io": {
      "type": "StdOutPrinter",
      "encoding": "UTF-8"
    },
    "observers": [
    ]
  }
}
```

## Logging

There are two different kinds of logging: RawDataLogger and GlobalLogger. Every device has a own logger-which writes received data to a logfile ``./log/<DeviceName>_raw.log``. The Global Logger writes general (debug-)info to ``./logs/main_log.log``.

### How much is logged

These logger are using RotatingFileHandler.

> Handler for logging to a set of files, which switches from one file to the next when the current file reaches a certain size.
>
>  logging.handlers.RotatingFileHandler

* Mode: append
* MaxSize per file (bytes): 5 * 1024 * 1024
* Amount of BackupFiles: 2



## Installation

To install this project you need a python-interpreter which support asynchronous programming. This should be working with Python >= 3.6.
Right now there is no wheel package available. Usually you could install it with `python3.<version> -m pip install nmea_seatalk_multiplexer.<package_version>.whl`

Right now though you need to copy theses project files to your target-machine and install the packages in [Dependencies](#Dependencies). Then start it as mentioned in [Invocation](#Invocation).


## Dependencies

Also mentioned in `setup.py`:

* curio >=1.0
* contextvars (site-dependency in curio)
* pyserial

To install these packages: h `python3.<version> -m pip install <package>`. (Ensure that curio has the correct version).