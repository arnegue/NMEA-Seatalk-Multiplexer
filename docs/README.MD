# Own Setup
This page describes my own configuration on an Orange Pi Zero.\
PDFs and PinOuts are also in this repository's branch.

# Used Hardware
## Orange Pi Zero
[Homepage Orange Pi Zero](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-Zero-LTS.html)

## Delock USB 2.0 to 4 x serial adapter
[Delock USB 2.0 to 4 x serial adapter Adapter Homepage](https://www.delock.de/produkt/87414/merkmale.html?setLanguage=en)

## Own soldered Seatalk-Serial converter:
[Thomas Knauf's layout](http://www.thomasknauf.de/rap/seatalk3.htm#Bid)

## Own soldered I2C-LED-Screen
This is not part of the main branch since it's not directly needed. All in all it's just five RGB-LEDs and one state-LED\ 
connected to a [PCF8575C](https://www.ti.com/lit/ds/symlink/pcf8575c.pdf)-Shield.

## Radio: Lowrance Link-8 VHF
* [Owner's Manual](https://softwaredownloads.navico.com/Lowrance/FTP/Lowrance_Software%20-%20Copy/Documents/Link-8_OM_EN_988-10254-001_w.pdf)
* [Installation instructions](ftp://software.lowrance.com/Documents/Link-8_IM_EN_988-10249-002_w.pdf)
## Wind: NASA Clipper Wireless Wind 
[User Manual](https://www.nasamarine.com/wp-content/uploads/2015/12/Clipper-Wireless-Wind.pdf)
## GPS: Evermore SA-920
[User Manual](https://media1.svb-media.de/media/snr/504148/pdf/manual_2016-04-15_08-12-59_2a4ee3b97a0ab407152b7afd32c439f0.pdf) (Link leads to media1.svb-media.de | Link is for SA-320, but pinout is similar, you could the correct manual from this repository though)

## Seatalk: Raymarine ST60+ Tridata
[Owner's Manual](http://busse-yachtshop.de/pdf/ray60Tridata.pdf)  (link leads to busse-yachtshop.de)

## Linux
I used the most recent [Armbian](https://www.armbian.com/orange-pi-zero/). Last version: Armbian 23.02 Bullseye
Every further command is executed as root.

## WiFi-HotSpot
To enable hotspot a WiFi-HotSpot, first install a DNS/DHCP-Server. Reboots may be required between steps
* `apt install dnsmasq` (https://askubuntu.com/a/1437049 may be needed) 
* `nmcli dev wifi hotspot ifname wlan0 ssid Armbian password "12345678"`
* `nmtui` -> Edit a connection -> hotspot -> X Automatically connect

## Interfaces
* Enable `/dev/ttyS2` for AIS:\
 `armbian-config` -> System -> Hardware -> uart2\
* Enable I2C for State-LEDs:\
`armbian-config` -> System -> Hardware -> i2c0

# Connector-PinOuts
If there are JST-XH-Pins: Numbering from notch-side-view.

## Common Adapters
### USB-Serial-Adapter
| Name | Color  | OrangePi-Pin | USB-Pin |
|------|--------|--------------|---------|
| 5V   | Red    | ? 5V         | 1       |
| Gnd  | Yellow | ? Gnd        | 4       |
| D-   | Brown  | ? USB-DM2    | 2       |
| D+   | Orange | ? USB-DP2    | 3       |

### Display-I2C
| Name | Color  | OrangePi-Pin | JST-Pin |
|------|--------|--------------|---------|
| 3v3  | Yellow | 01           | 1       |
| SDA  | Orange | 03           | 2       |
| SCL  | Red    | 05           | 3       |
| Gnd  | Brown  | 09           | 5       |

## Seatalk
### USB-Serial to Seatalk-circuit-board
| Name | Color  | Serial-Pin | JST-Pin |
|------|--------|------------|---------|
| RX   | Yellow | 2          | 2       |
| TX   | Red    | 3          | 3       |
| Gnd  | Blue   | 5          | 1       |

### Seatalk-circuit-board to DSUB9-connector
| Name | Color  | JST-Pin | DSUB9-Pin |
|------|--------|---------|-----------|
| 12v  | Red    | 1       | 5         |
| Data | Yellow | 2       | 3         |
| Gnd  | Blue   | 3       | 2         |

## GPS
### USB-Serial to DSUB9-connector
| Name | Color  | Serial-Pin | DSUB9-Pin |
|------|--------|------------|-----------|
| RX   | Yellow | 2          | 2         |
| TX   | Red    | 3          | 3         |
| Gnd  | Blue   | 5          | 5         |

## Radio
### USB-Serial to DSUB9-connector
| Name        | Color  | Serial-Pin | DSUB9-Pin |
|-------------|--------|------------|-----------|
| RX NMEA0183 | Yellow | 2          | 2         |
| TX NMEA0183 | Red    | 3          | 3         |
| Gnd         | Blue   | 5          | 5         |

### MAX-232 to DSUB9-Connector (AIS | RS422)
| Name   | Color  | JST-Pin | DSUB9-Pin |
|--------|--------|---------|-----------|
| RX AIS | Green  | 1       | 7         |
| Gnd    | White  | 2       | 6         |
| TX AIS | Black  | 3       | 9         |

### UART2 to MAX-232 (AIS | UART)
| Name     | Color | OrangePi-Pin | JST-Pin |
|----------|-------|--------------|---------|
| UART2_RX | Grey  | 11           | 3       |
| UART2_TX | White | 13           | 2       |

### Power to MAX-232 (MAX-232-Power for AIS)
| Name | Color | OrangePi-Pin | JST-Pin |
|------|-------|--------------|---------|
| 3v3  | Red   | 17           | 2       |
| Gnd  | Black | 25           | 1       |

## Wind
### USB-Serial to DSUB9-connector
| Name | Color  | Serial-Pin | DSUB9-Pin |
|------|--------|------------|-----------|
| RX   | Yellow | 2          | 2         |
| TX   | Red    | 3          | 3         |
| Gnd  | Blue   | 5          | 5         |

### Debug-UART (connected to Wind's DSUB9-Connector) 
| Name | Color  | OrangePi-Pin | DSUB9-Pin |
|------|--------|--------------|-----------|
| TX   | Orange | 1*           | 6         |
| RX   | Red    | 2*           | 7         |
| Gnd  | Brown  | 3*           | 9         |

\* Debug bridge pins next to ethernet port
