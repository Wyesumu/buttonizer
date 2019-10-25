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
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView

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

author_association = db.Table('author_association', db.Model.metadata,
	db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), primary_key=True),
	db.Column('author_id', db.Integer, db.ForeignKey('author.id'), primary_key=True)
)

class Author(db.Model):

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
	authors = db.relationship("Author", secondary=author_association, lazy='subquery',
							backref=db.backref('channel', lazy=True))

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
							backref=db.backref('button', lazy=True))

	def __str__(self):
		return self.text

class User(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)

db.create_all()

#flask-admin

class UserView(ModelView):
	column_exclude_list = ['password',]
	form_excluded_columns = ['password',]


admin = Admin(app)
admin.add_view(UserView(Author, db.session))
admin.add_view(UserView(User, db.session))
admin.add_view(UserView(Channel, db.session))
admin.add_view(UserView(Post, db.session))
admin.add_view(UserView(Button, db.session))

#bot
@app.route('/{}'.format(config.secret), methods=["POST"])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

#site start
#--------------------<session control>----------------------

@app.route("/login", methods=['GET', 'POST'])
def login():
	if flask.request.method == 'POST':
		#get data from form
		login = flask.request.form["login"] 
		password = flask.request.form["password"]
		user_data = Author.query.filter_by(username = login).first()
		if user_data is not None:
			if bcrypt.check_password_hash(user_data.password, str(password)): #compare user input and password hash from db
				#set session info in crypted session cookie
				flask.session['logged'] = "yes"
				flask.session['user_id'] = user_data.id
				return flask.redirect(flask.url_for("index"))
			else:
				flask.flash("Wrong password. Try again")
		else:
			flask.flash("Wrong Login. Try again")
	return flask.render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
	if flask.request.method == 'POST':
		f = flask.request.form.to_dict(flat=False) #get data from form
	
		if [''] in f.values(): #if there's any empty field
			flask.flash("Не все поля заполнены")
			return flask.redirect(flask.url_for("register"))
		elif f['password'][0] != f['password_check'][0]: #if passwords doesn't match
			flask.flash("Пароли не совпадают")
			return flask.redirect(flask.url_for("register"))
		elif f['pass_phrase'][0] != config.pass_phrase: #if passphrase is wrong
			flask.flash('Неверно введена кодовая фраза')
			return flask.redirect(flask.url_for("register"))
		else:
			#check if username already in db
			if Author.query.filter_by(username = f["login"][0]).first():
				flask.flash("Пользователь с таким именем уже существует")
				return flask.redirect(flask.url_for("register"))
			else:
				#create new user
				new_user = Author(username = f["login"][0], password = bcrypt.generate_password_hash(str(f["password"][0])))
				db.session.add(new_user)
				db.session.commit()

		return flask.redirect(flask.url_for("login"))
	else:
		return flask.render_template("register.html")

@app.route("/exit", methods=["GET"])
def exit():
	flask.session.clear() #clear session when user log out
	return flask.redirect(flask.url_for("login"))

#---------------------/session control/--------------------------

#bot start
@bot.message_handler(content_types=['photo', 'audio', 'sticker'])
def content_error(message):
    bot.send_message(message.chat.id, "Извините, я понимаю только текстовые сообщения и изображения, отправленные в виде файла")