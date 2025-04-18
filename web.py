import redis
from flask import Flask
from flask import render_template
from flask import jsonify


app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, db=0)


@app.route('/')
def get_home():
    return render_template('home.html')


@app.route('/data')
def get_data():
    data = {
        'motor_speed': float(r.get('motor_speed') or 0),
        'steps_count': int(r.get('steps') or 0)
    }
    return jsonify(data)


@app.route('/speed-up', methods=['POST'])
def set_speed_up():
    r.publish('slinky_channel', 'motor_speed_up')
    return jsonify({'result': True})


@app.route('/speed-down', methods=['POST'])
def set_speed_down():
    r.publish('slinky_channel', 'motor_speed_down')
    return jsonify({'result': True})


@app.route('/toggle-motor', methods=['POST'])
def set_toggle_motor():
    r.publish('slinky_channel', 'toggle_motor')
    return jsonify({'result': True})
