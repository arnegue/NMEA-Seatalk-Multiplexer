# NMEA-Seatalk-Multiplexer ![Test results](https://github.com/arnegue/NMEA-Seatalk-Multiplexer/actions/workflows/main.yml/badge.svg?branch=master)

Python-library for processing and multiplexing maritime device data from data-busses such as NMEA-0183 (+ AIS), Seatalk(1).
No need to (cross-)compile your project. Little dependencies. Easy configuratable.

- [NMEA-Seatalk-Multiplexer ](#nmea-seatalk-multiplexer-)
  - [Features](#features)
  - [Invocation](#invocation)
  - [Supported Interfaces](#supported-interfaces)
    - [NMEA 0183](#nmea-0183)
    - [Seatalk 1](#seatalk-1)
      - [Supported (and tested on ST50 and ST60) Seatalk-IDs:](#supported-and-tested-on-st50-and-st60-seatalk-ids)
      - [Implemented but untested (missing Equipment) Seatalk-IDs:](#implemented-but-untested-missing-equipment-seatalk-ids)
  - [Creating your devices](#creating-your-devices)
    - [TCP](#tcp)
      - [Server](#server)
      - [Client](#client)
    - [File](#file)
    - [FileRewriter](#filerewriter)
    - [Serial](#serial)
    - [SeatalkSerial](#seatalkserial)
      - [Parity Space/mark](#parity-spacemark)
      - [Settings](#settings)
    - [StdOutPrinter](#stdoutprinter)
  - [Logging](#logging)
  - [SettingTime](#settingtime)
  - [Watchdog](#watchdog)
    - [Windows](#windows)
    - [Linux](#linux)
    - [What's the interval](#whats-the-interval)
  - [Installation](#installation)
  - [Administrator](#administrator)
  - [Dependencies](#dependencies)

## Features

* Runs on Windows and Linux (Tested Windows 10, Armbian 4.19, Raspbian)
* Python >=3.6
* Easy logging for raw-data and "normal" logging
* Supported interfaces (both reading and writing):
  * NMEA
  * Seatalk
* Support for IO:
  * TCP (Client and Server)
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

Since this project only produces NMEA-Output every NMEA-Device is supported which produces a new line at the end.
 Usually no parsing (but checksum) is happening.

But some parsing/creations of NMEA-Sentences are supported:
* RMC (Recommended Minimum Sentence) 
* VHW (Speed Through Water)
* DBT (Depth Below Keel)
* MTW (Water Temperature) 
* MWV (Wind Speed and Angle)

### Seatalk 1
 
A big part of help for parsing Seatalk-Sentences and building hardware to be able to receive has come 
from [Thomas Knauf](http://www.thomasknauf.de/seatalk.htm). 

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
* 0x25 - Total & Trip Log
* 0x36 - Cancel MOB
* 0x38 - CodeLock Data
* 0x50 - Latitude
* 0x51 - Longitude
* 0x52 - Speed Over Ground
* 0x53 - Course Over Ground
* 0x54 - GMT-Time
* 0x55 - KeyStroke (1)
* 0x56 - Date
* 0x57 - Satellite Info
* 0x58 - Position
* 0x59 - Set Count Down Timer
* 0x61 - E80-Initialization
* 0x65 - Select Fathom
* 0x66 - Wind Alarm
* 0x68 - Alarm Acknowledgment Keystroke
* 0x6C - Equipment ID (2)
* 0x6E - Man Over Board
* 0x80 - Set Lamp Intensity (2)
* 0x81 - Course Computer Setup
* 0x86 - KeyStroke (2)
* 0x87 - Set Response Level
* 0x90 - Device Identification (2)
* 0x91 - Set Rudder Gain
* 0x93 - Enter AP-Setup
* 0x99 - Magnetic Variation
* 0xA4 - Device Identification (BroadCast, Termination, Answer)

(n) means there are multiple Datagrams with same/similar meaning.

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
  }
}
```

* The ``DeviceName`` is up to you but must be unique and is important for the ``observers``-section
* The ``type`` specifies the type of data the devices receive (currently only ``NMEADevice`` and ``SeatalkDevice`` is supported)
* Optional settings:
  * ``auto_flush: x``: Flushes IO every time every ``x`` datagrams were received.
  * ``max_item_age: x``: When dequeued item's age (since enqueueing) os older than ``x`` seconds, the item gets discarded. Defaults to 30 seconds

* ``device_io`` sets the IO-Settings needed for communication to that device (explained below).
  * Every ``device_io`` needs at least ``type`` to ensure which I/O to be used.
  * Settings ``encoding`` is optional for every ``device_io``
  * Every other settings given in that section depend on the ``type``
* The ``observer`` section contains a list of 0-to-n DeviceNames which observe this device (getting this device's data)


### TCP

You can create either a TCP-Server or a -Client

#### Server

This example creates a TCP-Server called "MyTCPServer" on port 9900 with ASCII-Encoding. This device's type is NMEADevice. 
So, it only transmits/receives NMEA-Strings.

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

Assumes **appending**-mode!

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

### FileRewriter

Similar to File but overwrites the file when writing and reading as much as possible.


### Serial

This may be the most important section.

* port - Serial-Port. Example Windows: "COM5" | Example Unix: "/dev/ttyS2"
* baudrate - default 4800
* bytesize - default 8
* stopbits - default 1
* parity - default None

Following example is a `Serial` device listening on ``/dev/ttyUSB0`` with ASCII-encoding and the default serial settings.
```json
{
  "GPS": {
    "type": "NMEADevice",
    "auto_flush": 10,
    "device_io": {
      "type": "Serial",
      "port": "/dev/ttyUSB1",
      "encoding": "ASCII"
    },
    "observers": [
      "TCP",
      "TimeSetter"
    ]
  }
}
```

### SeatalkSerial
`SeatalkSerial` is a special `Serial` DeviceIO, because of its command byte, reflected with a mark-parity bit, whereas
all other bytes have a space-parity (some may call it 9-bit serial).

#### Parity Space/mark
After further investigation: It can be tough to enable parity-checking. That's because of a mix of pyserial's
implementation but also how your OS handles parity bits. Not every RS232/UART-device supports Mark/Space parity (if at all).
> **Note**: 
> If your device does not support it (no messages gets received because of missing ParityException), use ``"type": "Serial"`` instead.

The parsing is worse (could be wrong too) because the program has to guess the command byte, but that's better than nothing.

#### Settings
Following example shows a Seatalk-Device on port ``/dev/ttyUSB3``.
No encoding is happening, so that the parsing is done on bit/byte-level.
Additionally, the observer "MyTCPServer" is listening to this device.
Furthermore, the IO gets flushed after 10 datagrams were received (set with optional ``auto_flush``).

```json
{ 
  "Seatalk": {
   "type": "SeatalkDevice", 
   "auto_flush": 10,
   "device_io": {
     "type": "SeatalkSerial",
     "port": "/dev/ttyUSB3"
   },
   "observers": [
     "MyTCPServer"
   ]
  }
}
```


### StdOutPrinter

This device just prints out to StdOut (StdIn currently not supported):

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

There are two different kinds of logging: RawDataLogger and GlobalLogger. Every device has an own logger-which writes 
received data to a logfile ``<DeviceName>_raw.log``. The Global Logger writes general (debug-)info to ``main_log.log``.

A [RotatingFileHandler](https://docs.python.org/3/library/logging.handlers.html) is used for logging. 
To change its default values and logfile-directory check ``config.json`` via ``Logger``

## SettingTime

Many devices don't have a battery driven RTC (real time clock) or similar which might be useful for logging. Luckily GPS provides some information about date and time: ``GPRMC`` (Recommended Minimum Sentence).
Besides positional data there are also some timing information. If you add a ``SetTimeDevice`` like this (don't forget to set ``TimeSetter`` as observer on the GPS-counterpart-device:

```json
{
  "TimeSetter": {
    "type": "SetTimeDevice", 
    "device_io": {
      "type": "IO"
    },
    "observers": [
    ]
  }
}
``` 
  
The first valid ``RMC`` sentence will be used to set system (and eventually hardware-time).

## Watchdog

Since I noticed some hardware/driver related errors, I implemented a watchdog.
If activated in ``config.json`` via ``Watchdog.Enable`` the watchdog will work within the ``TaskWatcher``.
The ``TaskWatcher`` is responsible to watch every (nearly) daemonic spawned tasks. These tasks shall not terminate. If so
the watchdog won't be reset, ``Watchdog.PreviousResets`` get incremented and an immediate system reset will happen.
The watchdog only gets started if enabled and ``Watchdog.PreviousResets`` is smaller than ``Watchdog.MaxResets`` to avoid bootloop.
If it is bigger or equal, it only gets logged. The reset of ``Watchdog.PreviousResets`` back to 0 has to be done manually.

 
### Windows 

The program simply checks via ``os.name`` if there is an ``nt``-system. If so a software watchdog is used. This is a simple
background running thread which checks every second if a timeout occurred. If so ``os.system("shutdown -t 0 -r -f")`` will
be initiated. 


### Linux

If you're on a Linux system, the watchdog in ``/dev/watchdog`` will be used. If you loaded the correct kernel module, a 
hardware watchdog will be used.

Note: This requires sudo-privilege. (It's also possible to use the Software-Watchdog, but why though?) 


### What's the interval

The watchdog **timeout** *can* be set in ``config.json`` via ``Watchdog.Timeout`` (disabled by default). It must be set for the Software-Watchdog. 
If the value is ``null`` for the Linux watchdog, the default timeout will be taken which is usually 16 seconds. 
The **interval** is responsible for that the watchdog timeout doesn't run out which triggers a reboot.
The **interval is set for half the timeout**.  


## Installation

To install this project, you need a python-interpreter which support asynchronous programming. This should be working with Python >= 3.5. But take a look at curio's dependencies!
There is no wheel package available. Usually you could install it with `python3.<version> -m pip install nmea_seatalk_multiplexer.<package_version>.whl`

Right now, though you need to copy theses project files to your target-machine and install the packages mentioned in [Dependencies](#Dependencies). Then start it as mentioned in [Invocation](#Invocation).

## Administrator

Features like [Watchdog](#Watchdog) and [SettingTime](#SettingTime) require admin privileges. If you don't use them the program should be running as standard user.

## Dependencies

Also mentioned in `setup.py`:

* curio >=1.0 (note comment from above, that newest curio-version needs Python 3.7 [[There seems to be a curio-problem with 3.12](https://github.com/dabeaz/curio/issues/367)])
* contextvars (site-dependency of curio)
* pyserial
* pywin32 (for Windows if ``SetTimeFromGPS`` is enabled)

To install these packages: `python3.<version> -m pip install <package>`. (Ensure that curio has the correct version).
