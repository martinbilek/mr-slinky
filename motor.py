import pigpio
import time

import redis


# Constants
MOTOR_STEP_PIN = 21
MOTOR_DIR_PIN = 20
MOTOR_ENABLE_PIN = 18

START_MOTOR_STEP_DELAY_SEC = 0.0005  # initial delay (motor speed)

SENSOR_BOTTOM_PIN = 27  # PIN of bottom sensor
SENSOR_TOP_PIN = 17     # PIN of top sensor

SPEED_CHANGE_INTERVAL = 1.5  # how often can be speed changed in seconds
DELAY_CONST_PCT = 1.05       # constant how much in percent is changed speed

SHUTDOWN_DELAY = 3.0  # delay, when motor is automatically
                      # powered off when TOP and BOTTOM sensor are without detection

STAIR_MOTOR_STEPS = 1231  # how many motor steps to travel one physical step


def create_step_waveform(pi, step_delay_sec):
    '''Helper function to create one repeating step waveform'''
    step_delay_us = int(step_delay_sec * 1_000_000)

    pi.wave_clear()

    wf = []
    wf.append(pigpio.pulse(1<<MOTOR_STEP_PIN, 0, step_delay_us))  # STEP high
    wf.append(pigpio.pulse(0, 1<<MOTOR_STEP_PIN, step_delay_us))  # STEP low

    pi.wave_add_generic(wf)
    wave_id = pi.wave_create()
    return wave_id


def set_motor_speed(pi, step_delay_sec):
    '''Heleper function to start motor or change motor speed'''
    # clear any old motor waves
    stop_motor(pi)

    # enable motor - in case it was not running before
    pi.write(MOTOR_ENABLE_PIN, 0)

    print('Changing speed...')

    # Create and start new wave
    wave = create_step_waveform(pi, step_delay_sec)
    pi.wave_send_repeat(wave)


def stop_motor(pi):
    '''Stop motor'''
    pi.wave_tx_stop()  # stop old wave
    pi.wave_clear()    # clear old wave


def main():
    # Connect to pigpio
    pi = pigpio.pi()
    if not pi.connected:
        print('Error: pigpio not connected...')
        exit()

    # connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0)

    # sensors detection variables
    last_top_time = time.time()       # time, when was object indicated on top sensor
    last_bottom_time = time.time()    # time, when was object indicated on bottom sensor
    top_detected = True               # indicates whether object is detected on top sensor during
    bottom_detected = True            # indicates whether object is detected on bottom sensor during

    speed_changed = True              # indicates whether speed has been changed in previous cycle already

    step_log_interval = 1.5
    step_last_log_time = time.time()

    try:
        # Setup motor
        pi.set_mode(MOTOR_DIR_PIN, pigpio.OUTPUT)     # direction PIN
        pi.set_mode(MOTOR_STEP_PIN, pigpio.OUTPUT)    # step PIN
        pi.set_mode(MOTOR_ENABLE_PIN, pigpio.OUTPUT)  # enable PIN
        pi.write(MOTOR_DIR_PIN, 0)                    # set motor direction

        # Setup sensors
        pi.set_mode(SENSOR_BOTTOM_PIN, pigpio.INPUT)
        pi.set_mode(SENSOR_TOP_PIN, pigpio.INPUT)

        step_delay_sec = START_MOTOR_STEP_DELAY_SEC
        last_step_delay_sec = 1000

        average_step_delay_sec = START_MOTOR_STEP_DELAY_SEC  # calculated average delay between steps of motor
        average_step_delay_count = 1                         # from how much values is average delay calculated? needed to calculate average when new numbers coming

        is_stopped = False

        motor_steps_accumulated = 0  # count how many motor steps passed
        last_waveform_check = time.time()

        while True:

            # top sensor dection
            if not top_detected and pi.read(SENSOR_TOP_PIN) == 0:
                last_top_time = time.time()
                top_detected = True
                speed_changed = False
            if time.time() - last_top_time > SPEED_CHANGE_INTERVAL:
                top_detected = False # after specified time detection is considered false

            # bottom sensor dection
            if not bottom_detected and pi.read(SENSOR_BOTTOM_PIN) == 0:
                last_bottom_time = time.time()
                bottom_detected = True
                speed_changed = False
            if time.time() - last_bottom_time > SPEED_CHANGE_INTERVAL:
                bottom_detected = False # after specified time detection is considered false

            if top_detected and bottom_detected:
                step_delay_sec = average_step_delay_sec

            # only bottom detected > speed up
            elif not top_detected and bottom_detected:
                if not speed_changed:
                    step_delay_sec = step_delay_sec / DELAY_CONST_PCT

            # only top detected > speed down
            elif not bottom_detected and top_detected:
                if not speed_changed:
                    step_delay_sec = step_delay_sec * DELAY_CONST_PCT

            # change motor speed when step delay changed from previous cycle
            if step_delay_sec != last_step_delay_sec:
                speed_changed = True
                last_step_delay_sec = step_delay_sec
                set_motor_speed(pi, step_delay_sec)

                if is_stopped:
                    motor_steps_accumulated = 0
                    last_waveform_check = time.time()

                is_stopped = False

            if not is_stopped:
                if not top_detected and not bottom_detected:
                    if time.time() - last_top_time > SHUTDOWN_DELAY and time.time() - last_bottom_time > SHUTDOWN_DELAY:
                        # reset speed to default to adapt speed to different slinky faster
                        step_delay_sec = START_MOTOR_STEP_DELAY_SEC
                        last_step_delay_sec = START_MOTOR_STEP_DELAY_SEC
                        average_step_delay_sec = START_MOTOR_STEP_DELAY_SEC
                        average_step_delay_count = 1
                        top_detected = False
                        bottom_detected = False

                        print('Stopping motor...')
                        stop_motor(pi)
                        is_stopped = True
                        pi.write(MOTOR_ENABLE_PIN, 1)  # disable motor

                # Calculate steps
                now = time.time()
                elapsed = now - last_waveform_check
                # How many motor steps happened since last check
                motor_frequency = 1 / (2 * step_delay_sec)
                motor_steps_passed = elapsed * motor_frequency
                motor_steps_accumulated += motor_steps_passed
                # If accumulated motor steps reach 1231 => 1 slinky step
                while motor_steps_accumulated >= STAIR_MOTOR_STEPS:
                    motor_steps_accumulated -= STAIR_MOTOR_STEPS
                    r.set('steps', int(r.get('steps') or 0) + 1)  # add one step
                last_waveform_check = now

                # log to redis currnet step avg time in seconds
                if time.time() - step_last_log_time >= step_log_interval:
                    time_per_step_sec = STAIR_MOTOR_STEPS * (2 * step_delay_sec)
                    r.set('time_per_step_sec', time_per_step_sec)
                    step_last_log_time = time.time()

            average_step_delay_count += 1
            average_step_delay_sec = average_step_delay_sec + (step_delay_sec - average_step_delay_sec) / average_step_delay_count

            time.sleep(0.1)

    except KeyboardInterrupt:
        print('Stopping motor script...')
    finally:
        stop_motor(pi)
        pi.write(MOTOR_ENABLE_PIN, 1)  # disable motor
        pi.stop()


if __name__ == '__main__':
    main()
