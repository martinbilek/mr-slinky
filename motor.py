import redis

import time
import RPi.GPIO as GPIO

import threading
import queue


# Redis
r = redis.Redis(host='localhost', port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe('slinky_channel')
redis_queue = queue.Queue()


# Constants
START_DELAY = 0.0006         # initial delay (motor speed)
DIR = 20                     # Direction GPIO Pin
STEP = 21                    # Step GPIO Pin
ENABLE_PIN = 18              # Enable step motor GPIO Pin
CW = 1                       # Clockwise Rotation
CCW = 0                      # Counterclockwise Rotation

ENABLE_SENSORS = True        # whether automatic speed sensors are enabled

SENSOR_BOTTOM_PIN = 27       # PIN of bottom sensor
SENSOR_TOP_PIN = 17          # PIN of top sensor

MAX_DELAY = 0.001            # maximum delay for step motor between steps
MIN_DELAY = 0.0001           # minimum delay for step motor between steps
DELAY_CONST_PCT = 1.05       # constant how much in percent is changed speed
SPEED_CHANGE_INTERVAL = 1.5  # how often can be speed changed in seconds

STEP_CYCLES_COUNT = 1231     # number of motor steps needed to run one elevator step

PUBSUB_CHECK_INTERVAL = 5.0  # to save time/CPU we only check redis pubsub messages channel once per specified time in seconds

SHUTDOWN_DELAY = 3.0         # delay, when motor is automatically
                             # powerd off when TOP and BOTTOM sensor are without signal


# Variables
is_running = True                 # indicates whether motor is running
last_top_time = time.time()       # time, when was object indicated on top sensor
last_bottom_time = time.time()    # time, when was object indicated on bottom sensor
top_detected = True               # indicates whether object is detected on top sensor during 
bottom_detected = True            # indicates whether object is detected on bottom sensor during 
speed_changed = True              # indicates whether speed has been changed in previous cycles already
average_delay = START_DELAY       # calculated average delay between steps of motor
average_count = 1                 # from how much values is average delay calculated? needed to calculate average when new numbers coming
cycles = 0                        # how many motor steps is already done
delay = 0.0                       # delay value


def redis_worker():
    while True:
        # store delay value in Redis
        r.set('motor_speed', delay)
        r.set('motor_avg_speed', average_delay)

        # read control messages comming from outside (i.e. from frontend interface)
        msg = pubsub.get_message()
        if msg and msg['type'] == 'message':
            cmd = msg['data'].decode()
            if cmd == 'toggle_motor': # toggle motor messsage received
                toggle_motor()

        # store step value in redis
        if redis_queue.qsize() > 0 and redis_queue.get() == 'add_step':
            _steps = int(r.get('steps') or 0)
            _steps += 1
            r.set('steps', _steps)

        time.sleep(0.5)


def toggle_motor():
    global is_running, \
        last_top_time, \
        last_bottom_time, \
        top_detected, \
        bottom_detected, \
        average_delay, \
        average_count
    is_running = not is_running
    last_top_time = time.time()
    last_bottom_time = time.time()
    top_detected = True
    bottom_detected = True
    average_delay = START_DELAY
    average_count = 1


def speed_down_motor():
    global delay
    _delay = delay * DELAY_CONST_PCT
    if _delay > MAX_DELAY:
        _delay = MAX_DELAY
    delay = _delay


def speed_up_motor():
    global delay
    _delay = delay / DELAY_CONST_PCT
    if _delay < MIN_DELAY:
        _delay = MIN_DELAY
    delay = _delay


def main():
    global delay, \
        cycles, \
        last_top_time, \
        last_bottom_time, \
        top_detected, \
        bottom_detected, \
        speed_changed, \
        average_delay, \
        average_count

    threading.Thread(target=redis_worker, daemon=True).start()

    try:
        # disable GPIO warnings
        GPIO.setwarnings(False)

        # configure motor
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DIR, GPIO.OUT)
        GPIO.setup(STEP, GPIO.OUT)
        GPIO.output(DIR, CCW)  # motor direction

        # SENSOR - bottom
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_BOTTOM_PIN, GPIO.IN)

        # SENSOR - top
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_TOP_PIN, GPIO.IN)

        # ENABLE MOTOR PIN - default is disabled
        GPIO.setup(18, GPIO.OUT)
        GPIO.output(18, GPIO.HIGH)

        while True:
            if is_running:
                GPIO.output(18, GPIO.LOW) # motor is enabled

                if cycles > STEP_CYCLES_COUNT and cycles % STEP_CYCLES_COUNT == 0:
                    # add slinky step
                    redis_queue.put('add_step')

                cycles += 1

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
                        speed_up_motor()

                if not bottom_detected and top_detected:
                    if not speed_changed and ENABLE_SENSORS:
                        speed_changed = True
                        speed_down_motor()

                if top_detected and bottom_detected:
                    delay = average_delay

                if not top_detected and not bottom_detected:
                    if time.time() - last_top_time > SHUTDOWN_DELAY and time.time() - last_bottom_time > SHUTDOWN_DELAY:
                        toggle_motor()

                average_count += 1
                average_delay = average_delay + (delay - average_delay) / average_count


                GPIO.output(STEP, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(STEP, GPIO.LOW)
                time.sleep(delay)
            else:
                GPIO.output(18, GPIO.HIGH) # motor is disabled
                time.sleep(0.5)

    except KeyboardInterrupt:
        print('Stopping motor script...')
    finally:
        GPIO.cleanup()


if __name__ == '__main__':
    main()
