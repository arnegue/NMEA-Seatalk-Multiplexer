# Own Setup
This page describes my own configuration on an Orange Pi Zero.\
PDFs and PinOuts are also in this repository's branch.

# Used Hardware
## Orange Pi Zero 2
[Raspberry Pi Zero 2W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)

(Previously I used an Orange Pi Zero, but I needed UART with support for parity Space/Mark)

## Delock USB 2.0 to 4 x serial adapter
Don't use it for seatalk. It Parity Mark/Space is not supported
[Delock USB 2.0 to 4 x serial Adapter Homepage](https://www.delock.de/produkt/87414/merkmale.html?setLanguage=en)

## Own soldered Seatalk-Serial converter:
[Thomas Knauf's layout](http://www.thomasknauf.de/rap/seatalk3.htm#Bid)

## Radio: Lowrance Link-8 VHF
* [Owner's Manual](https://softwaredownloads.navico.com/Lowrance/FTP/Lowrance_Software%20-%20Copy/Documents/Link-8_OM_EN_988-10254-001_w.pdf)
* [Installation instructions](ftp://software.lowrance.com/Documents/Link-8_IM_EN_988-10249-002_w.pdf)

## Wind: NASA Clipper Wireless Wind 
[User Manual](https://www.nasamarine.com/wp-content/uploads/2015/12/Clipper-Wireless-Wind.pdf)

## GPS: Evermore SA-920
[User Manual](https://media1.svb-media.de/media/snr/504148/pdf/manual_2016-04-15_08-12-59_2a4ee3b97a0ab407152b7afd32c439f0.pdf) (Link leads to media1.svb-media.de | Link is for SA-320, but pinout is similar)

## Seatalk: Raymarine ST60+ Tridata
[Owner's Manual](http://busse-yachtshop.de/pdf/ray60Tridata.pdf)  (link leads to busse-yachtshop.de)

## AIS: AIS Transceiver
[User Manual](https://www.alltekmarine.com/uploads/download_list/16831862301951116903.pdf)

## Linux
I used the most recent [Armbian](https://www.armbian.com/orange-pi-zero-2/). Latest version: Armbian 23.02 Bullseye
Every following command is executed as root.


## WiFi-HotSpot
To enable hotspot a WiFi-HotSpot, first install a DNS/DHCP-Server. Reboots may be required between steps
* `apt install dnsmasq` (https://askubuntu.com/a/1437049 may be needed) 
* `nmcli dev wifi hotspot ifname wlan0 ssid Armbian password "12345678"`
* `nmcli connection modify Hotspot ipv4.addresses "172.24.0.1/24"`
* `nmtui` -> Edit a connection -> hotspot -> X Automatically connect


# Connector-PinOuts
If there are JST-XH-Pins: Numbering from notch-side-view.

## Seatalk
### Seatalk-circuit-board to Casing DSUB9-connector
| Name | Color  | JST-Pin | DSUB9-Pin |
|------|--------|---------|-----------|
| Gnd  | Yellow | 1       | 2         |
| 12v  | Red    | 2       | 5         |
| Data | Blue   | 3       | 3         |

### Seatalk-circuit-board to RaspberryPi-Connector
| Name | Color | JST-Pin | RaspberryPi-Pin  |
|------|-------|---------|------------------|
| Gnd  | Black | 1       | 6 (Gnd)          |
| 3v3  | Red   | 2       | 1 (3v3)          |
| Rx   | Green | 3       | 10 (Rx, GPIO 15) |
| Tx   | White | 4       | 8 (Tx, GPIO 14)  |


## AIS
### AIS RS422 Adapter to Casing DSUB9-connector
| Name | Color | RS422 Adapter | Casing DSUB9-Pin |
|------|-------|---------------|------------------|
| Rx+  | Red   | Y (1)         | 6                |
| Rx-  | White | Z (2)         | 7                |
| Tx+  | Green | B (3)         | 8                |
| Tx-  | Black | A (4)         | 9                |

### AIS RS422 Adapter to AIS MAX-232 JST-Connector
| Name | Color  | RS422 Adapter | JST-Pin |
|------|--------|---------------|---------|
| Gnd  | Yellow | 2             | 1       |
| 3v3  | Red    | 1             | 2       |
| Rx   | Green  | 3             | 4       |
| Tx   | Blue   | 4             | 3       |

### AIS MAX-232 JST-Connector to USB-Serial DSUB9-connector
| Name | Color  | JST-Pin       | DSUB9-connector  |
|------|--------|---------------|------------------|
| Gnd  | Blue   | 1             | 5                |
| Rx   | Yellow | 2             | 2                |
| Tx   | Red    | 3             | 3                |


## Radio
### USB-Serial DSUB9-connector to Casing DSUB9-connector
| Name        | Color  | Serial-Pin | DSUB9-Pin |
|-------------|--------|------------|-----------|
| RX NMEA0183 | Yellow | 2          | 2         |
| TX NMEA0183 | Red    | 3          | 3         |
| Gnd         | Blue   | 5          | 5         |


## Wind
### USB-Serial DSUB9-connector to Casing DSUB9-connector
| Name | Color  | Serial-Pin | DSUB9-Pin |
|------|--------|------------|-----------|
| RX   | Yellow | 2          | 2         |
| TX   | Red    | 3          | 3         |
| Gnd  | Blue   | 5          | 5         |


# Test-Device PinOuts
## Raymarine RC300
### Seatalk-Socket
```
  _______
 /1  2  3 \
|   ___   |
 \_/   \_/
```
| Name  | Seatalk-Socket |
|-------|----------------|
| (12V) | 1              |
| Gnd   | 2              |
| Data  | 3              |


### NMEA-Power-Connector
```
   ________
  / 6 || 1 \
 |5       2|
 \_4_____3_/
```

| Name       | NMEA-Power-Connector |
|------------|----------------------|
| NMEA Out - | 1                    |
| NMEA Out + | 2                    |
| NMEA In -  | 3                    |
| NMEA In +  | 4                    |
| 12 V       | 5                    |
| Gnd        | 6                    |

## AdvanSea C.56
### NMEA-2K-Connector
```
   ________
  / 1 || 4 \
 |    5    |
 \_2_____3_/
```

| Name                              | NMEA-2k-Connector |
|-----------------------------------|-------------------|
| Shield                            | 1                 |
| Net-H (CAN-High)                  | 2                 |
| Net-C (Gnd)                       | 3                 |
| Net-S (12 V, NEED TO BE APPLIED!) | 4                 |
| Net-L (CAN-Low)                   | 5                 |
