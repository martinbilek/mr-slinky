#!/usr/bin/env python3

from apa102_pi.colorschemes import colorschemes


NUM_LED = 17
BRIGHTNESS = 15


def main():
    print('One slow trip through the rainbow')
    my_cycle = colorschemes.Rainbow(num_led=NUM_LED, pause_value=0.1,
                                    num_steps_per_cycle=100, num_cycles=9999999, order='rgb', global_brightness=BRIGHTNESS)
    my_cycle.start()


if __name__ == '__main__':
    main()
