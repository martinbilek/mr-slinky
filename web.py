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
        'motor_speed': float(r.get('motor_speed') or -1.0),
        'motor_avg_speed': float(r.get('motor_avg_speed') or -1.0),
        'steps_count': int(r.get('steps') or -1.0)
    }
    return jsonify(data)


@app.route('/toggle-motor', methods=['POST'])
def set_toggle_motor():
    r.publish('slinky_channel', 'toggle_motor')
    return jsonify({'result': True})
