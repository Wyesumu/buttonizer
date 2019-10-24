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

bot = telebot.TeleBot(config.token, threaded=False)
bot.set_webhook(config.addr)

app = flask.Flask(__name__)

bcrypt = Bcrypt(app)
app.secret_key = config.secret

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://'+config.db_user+':'+config.db_pass+'@'+config.db_host+'/'+config.db_name + '?charset=utf8mb4'
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
db = SQLAlchemy(app)

user_association = db.Table('user_association', db.Model.metadata,
	db.Column('button_id', db.Integer, db.ForeignKey('button.id'), primary_key=True),
	db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class Admin(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(255))
	password = db.Column(db.String(255))
	privileges = db.Column(db.Integer, default = 5)

	def __str__(self):
		return self.username

class Channel(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(255, collation='utf8_unicode_ci'))
	posts = db.relationship('Post', backref='channel', lazy=True)

	def __str__(self):
		return self.name

class Post(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String(255, collation='utf8_unicode_ci'))
	image_addr = db.Column(db.String(255, collation='utf8_unicode_ci'))
	chanel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=False)
	buttons = db.relationship('Button', backref='post', lazy=True)

	def __str__(self):
		return self.text

class Button(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String(255, collation='utf8_unicode_ci'))
	details = db.Column(db.String(255, collation='utf8_unicode_ci'))
	post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
	users = db.relationship("User", secondary=user_association, lazy='subquery',
							backref=db.backref('users', lazy=True))

	def __str__(self):
		return self.text

class User(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)

db.create_all()

@app.route('/{}'.format(config.secret), methods=["POST"])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)