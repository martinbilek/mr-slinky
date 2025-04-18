import redis

import time
import RPi.GPIO as GPIO


r = redis.Redis(host='localhost', port=6379, db=0)

IS_RUNNING = True        # indicates whether motor is running
START_DELAY = 0.0006     # initial delay (motor speed)


has_delay_changed = True
cached_delay = 0.0
def getDelay():
    global cached_delay
    global has_delay_changed
    if has_delay_changed:
        cached_delay = float(r.get('motor_speed') or START_DELAY)
    has_delay_changed = False
    return cached_delay


def setDelay(delay):
    global has_delay_changed
    if cached_delay != delay:
        has_delay_changed = True
        r.set('motor_speed', delay)


def main():
    try:
        global IS_RUNNING

        DIR = 20             # Direction GPIO Pin
        STEP = 21            # Step GPIO Pin
        CW = 1               # Clockwise Rotation
        CCW = 0              # Counterclockwise Rotation

        BTN_RUN = 26         # BTN to run/stop motor
        BTN_SPEED_UP = 6     # BTN to speed up
        BTN_SPEED_DOWN = 5   # BTN to speed down

        GPIO.setwarnings(False)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DIR, GPIO.OUT)
        GPIO.setup(STEP, GPIO.OUT)
        GPIO.output(DIR, CW)


        ENABLE_SENSORS = True

        # SENSOR - bottom
        SENSOR_BOTTOM_PIN = 27
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_BOTTOM_PIN, GPIO.IN)

        # SENSOR - top
        SENSOR_TOP_PIN = 17
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_TOP_PIN, GPIO.IN)



        SHUTDOWN_DELAY = 4.0


        MAX_DELAY = 0.001
        MIN_DELAY = 0.0001
        DELAY_CONST_PCT = 1.0004
        DELAY_CONST_PCT = 1.018
        DELAY_CONST_PCT = 1.05


        SPEED_CHANGE_INTERVAL = 3


        def btn_run_callback(channel):
            global IS_RUNNING
            IS_RUNNING = not IS_RUNNING
        GPIO.setup(BTN_RUN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(BTN_RUN,GPIO.RISING,callback=btn_run_callback, bouncetime=300)


        def btn_speed_up_callback(channel):
            _delay = getDelay()
            _delay = _delay * DELAY_CONST_PCT
            if _delay > MAX_DELAY:
                _delay = MAX_DELAY
            setDelay(_delay)
        GPIO.setup(BTN_SPEED_UP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(BTN_SPEED_UP,GPIO.RISING,callback=btn_speed_up_callback, bouncetime=300)


        def btn_speed_down_callback(channel):
            _delay = getDelay()
            _delay = _delay / DELAY_CONST_PCT
            if _delay < MIN_DELAY:
                _delay = MIN_DELAY
            setDelay(_delay)
        GPIO.setup(BTN_SPEED_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(BTN_SPEED_DOWN,GPIO.RISING,callback=btn_speed_down_callback, bouncetime=300)


        # set motor direction
        GPIO.output(DIR, CCW)


        last_top_time = time.time()
        last_bottom_time = time.time()

        top_detected = True
        bottom_detected = True

        speed_changed = True



        average_delay = getDelay()
        average_count = 1



        STEP_CYCLES_COUNT = 1231
        cycles = 0

        while True:
            delay = getDelay()
            if cycles % STEP_CYCLES_COUNT == 0:
                print('Step:', cycles/STEP_CYCLES_COUNT, 'SPEED:', delay)
            cycles += 1

            if IS_RUNNING:

                if not top_detected and GPIO.input(SENSOR_TOP_PIN) == GPIO.LOW:
                    last_top_time = time.time()
                    top_detected = True
                    speed_changed = False
                if time.time() - last_top_time > SPEED_CHANGE_INTERVAL:
                    top_detected = False

                if not bottom_detected and GPIO.input(SENSOR_BOTTOM_PIN) == GPIO.LOW:
                    last_bottom_time = time.time()
                    bottom_detected = True
                    speed_changed = False
                if time.time() - last_bottom_time > SPEED_CHANGE_INTERVAL:
                    bottom_detected = False

                if not top_detected and bottom_detected:
                    if not speed_changed and ENABLE_SENSORS:
                        speed_changed = True
                        btn_speed_down_callback(None)
                        print('AVG/COUNT: %s / %s \n' % (average_delay, average_count))

                if not bottom_detected and top_detected:
                    if not speed_changed and ENABLE_SENSORS:
                        speed_changed = True
                        btn_speed_up_callback(None)
                        print('AVG/COUNT: %s / %s \n' % (average_delay, average_count))

                if top_detected and bottom_detected:
                    delay = average_delay
                    setDelay(delay)

                if not top_detected and not bottom_detected:
                    if time.time() - last_top_time > SHUTDOWN_DELAY and time.time() - last_bottom_time > SHUTDOWN_DELAY:
                        IS_RUNNING = False

                average_count += 1
                average_delay = average_delay + (delay - average_delay) / average_count


                GPIO.output(STEP, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(STEP, GPIO.LOW)
                time.sleep(delay)
            else:
                time.sleep(1)

                average_delay = START_DELAY
                average_count = 1

    except KeyboardInterrupt:
        print('Stopping motor script')
    finally:
        GPIO.cleanup()


if __name__ == '__main__':
    main()

