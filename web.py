import redis
from flask import Flask
from flask import render_template
from flask import jsonify


app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, db=0)


@app.route('/')
def getHome():
    return render_template('home.html')


@app.route('/data')
def getData():
    data = {
        'motor_speed': float(r.get('motor_speed') or 0),
        'steps_count': int(r.get('steps_count') or 0)
    }
    return jsonify(data)


@app.route('/speed-up', methods=['POST'])
def setSpeedUp():
    speed = float(r.get('motor_speed'))
    speed = speed * 1.1
    r.set('motor_speed', speed)
    return 'zrychleno na %s' % (speed,)
