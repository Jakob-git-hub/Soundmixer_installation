import machine
import utime
from machine import Pin, ADC
ADC_PINS = [26, 27]
RAW_ADC_MAX = 65535
from machine import I2C, Pin
from ads1x15 import ADS1115
adcs = [ADC(Pin(p)) for p in ADC_PINS]
RAW_THRESHOLD = 1600 
i2c=I2C(1, sda=Pin(10), scl=Pin(11))
adc = ADS1115(i2c, address=72, gain=1)
NUM_SLIDERS = 5
analogSliderValues = [0,0,0,0,0]

ADS_MAX_RAW = 21620 # Maximaler positiver Rohwert für ADS1115



PICO_MAX_RAW = 65535 # Maximaler Rohwert (read_u16)

# --- SKALIERUNGSKONSTANTEN ---
# Diese werden für die neuen Skalierungsfunktionen benötigt.
SCALE_FACTOR_PICO = 100.0 / PICO_MAX_RAW
SCALE_FACTOR_ADS = 100.0 / ADS_MAX_RAW
def scale_pico_raw(raw_value):
    """Skaliert den 16-Bit Rohwert des Pico ADC (0-65535) auf 0-100 und invertiert den Wert (0-Raw -> 100-Skaliert)."""
    scaled_value = int(raw_value * SCALE_FACTOR_PICO)
    # Invertierung: 100 - Skalierter Wert
    inverted_scaled_value = 100 - scaled_value 
    # Begrenzung auf 0-100
    return min(100, max(0, inverted_scaled_value))

def scale_ads_raw(raw_value):
    """Skaliert den 16-Bit Rohwert des ADS1115 (0-32767) auf 0-100."""
    # Sicherstellen, dass der Wert nicht negativ ist (0 bis 32767)
    positive_raw = max(0, raw_value)
    scaled_value = 100 - int(positive_raw * SCALE_FACTOR_ADS)
    # Begrenzung auf 0-100
    return min(100, max(0, scaled_value))

def updateSliderValues():
    for x in range(NUM_SLIDERS):
        if(x==0):
            analogSliderValues[0] = scale_ads_raw(adc.read(0,x))
        elif(x==1):
            analogSliderValues[1] = scale_ads_raw(adc.read(0,x))
        elif(x==2):
            analogSliderValues[2] = scale_ads_raw(adc.read(0,x))
        elif(x==3):
            analogSliderValues[3] = scale_pico_raw(adcs[0].read_u16())
        elif(x==4):
            analogSliderValues[4] = scale_pico_raw(adcs[1].read_u16())

# Make a string with all slider values and print it
def sendSliderValues():
    builtString = ""
    
    for x in range(NUM_SLIDERS):
        builtString +=  str(analogSliderValues[x])
        
        if(x < NUM_SLIDERS - 1):
            builtString += '|'
    
    print(builtString)


while(True):
    updateSliderValues()
    sendSliderValues()
    utime.sleep(0.01)
