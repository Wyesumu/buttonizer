import telebot
import flask
from functools import wraps
#sqlalchemy
from flask_sqlalchemy import SQLAlchemy
import pymysql.cursors
#custom config
import config
#datetime
from datetime import datetime as dt
#from datetime import date, timedelta
#crypt for user's password
from flask_bcrypt import Bcrypt

'''
Connection
'''
proxy_url = "http://proxy.server:3128"
bot = telebot.TeleBot(config.token, threaded=False)
bot.set_webhook("https://Wyesumu.pythonanywhere.com/{}".format(config.secret))

app = flask.Flask(__name__)

bcrypt = Bcrypt(app)
app.secret_key = config.secret_key

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://'+config.db_user+':'+config.db_pass+'@'+config.db_host+'/'+config.db_name + '?charset=utf8mb4'
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
db = SQLAlchemy(app)




@app.route('/{}'.format(config.secret), methods=["POST"])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)