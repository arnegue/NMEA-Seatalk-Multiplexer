from setuptools import setup

setup(
    name='nmea_seatalk_multiplexer',
    version='1.0',
    url='https://github.com/arnegue/NMEA-Seatalk-Multiplexer/',
    license='',
    author='Frosty',
    author_email='',
    description='Multiplatform NMEA and Seatalk parsing and multiplexing library written in pure Python',
    install_requires=['curio>=1.0',
                      'pyserial',
                      'pywin32 >= 1.0 ; platform_system=="Windows"'],
    extras_require={
        'tests': ['pytest']
    },
    py_modules=["nmea", "logs", "common", "seatalk"]
)
