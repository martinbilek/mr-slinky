#!/usr/bin/env python3

import time
import random
from apa102_pi.driver import apa102

import redis

# Constants
NUM_LEDS = 17
FLASH_BRIGHTNESS = 250           # max brightness during flash
FADE_STEPS = 10                 # how many steps to fade
FADE_TIME = 0.2                 # total fade duration (seconds)
DEFAULT_UPDATE_INTERVAL = 1.09  # seconds between steps

def random_color():
    '''Generate random color'''
    return random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)

def set_color(strip, r, g, b, brightness):
    '''Helper to set all LEDs to same color and brightness'''
    for i in range(NUM_LEDS):
        strip.set_pixel(i, r, g, b, brightness)
    strip.show()

def fade_brightness(strip, r1, g1, b1, r2, g2, b2):
    '''Fade brightness and color from color1 to color2'''
    for step in range(FADE_STEPS):
        ratio = (step + 1) / FADE_STEPS
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        brightness = int(FLASH_BRIGHTNESS * (1 - ratio))  # fade down brightness
        if brightness < 1:
            brightness = 1  # minimum brightness

        set_color(strip, r, g, b, brightness)
        time.sleep(FADE_TIME / FADE_STEPS)

def main():
    strip = apa102.APA102(num_led=NUM_LEDS)
    r = redis.Redis(host='localhost', port=6379, db=0)

    try:
        while True:
            update_interval = float(r.get('time_per_step_sec') or DEFAULT_UPDATE_INTERVAL)

            # Pick random flash color
            r1, g1, b1 = random_color()

            # Pick next background color
            r2, g2, b2 = random_color()

            # Flash bright color
            set_color(strip, r1, g1, b1, FLASH_BRIGHTNESS)
            time.sleep(0.2)  # strong flash

            # Fade to new color + dim brightness
            fade_brightness(strip, r1, g1, b1, r2, g2, b2)

            # Wait until next step
            remaining_time = update_interval - FADE_TIME - 0.25
            if remaining_time > 0:
                time.sleep(remaining_time)

    except KeyboardInterrupt:
        print('Stopping LED animation...')
    finally:
        # Turn off all LEDs
        for i in range(NUM_LEDS):
            strip.set_pixel(i, 0, 0, 0)
        strip.show()
        strip.cleanup()

if __name__ == '__main__':
    main()
