import curio
import seatalk
#from device_indicator import pin, led_device_indicator
import serial

TCP_PIN_R = 14
TCP_PIN_G = 7
TCP_PIN_B = 6

# USB0 Radio
# USB 1
# USB2 Wind
# USB3 Seatalk


async def main():
    st = seatalk.SeatalkDevice("Seatalk", port="COM10")
    await st.initialize()
    while 1:
        nmea_sentence = await st.get_nmea_sentence()
        if nmea_sentence:
            print(nmea_sentence)


curio.run(main)