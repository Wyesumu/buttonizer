import telebot
import flask
from functools import wraps
#sqlalchemy
from flask_sqlalchemy import SQLAlchemy
#custom config
import config
import os
#datetime
from datetime import datetime as dt
from time import time
#from datetime import date, timedelta
#crypt for user's password
from flask_bcrypt import Bcrypt
from flask_admin import Admin, AdminIndexView
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

#-------------------<database>---------------------------

db = SQLAlchemy(app)

user_association = db.Table('user_association', db.Model.metadata,
	db.Column('button_id', db.Integer, db.ForeignKey('button.id'), primary_key=True),
	db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

user_post_association = db.Table('user_post_association', db.Model.metadata,
	db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
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
	channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=False)
	buttons = db.relationship('Button', backref='post', lazy=True)
	date = db.Column(db.DateTime)
	users = db.relationship("User", secondary=user_post_association, lazy='subquery',
							backref=db.backref('post', lazy=True))

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
		return str(self.id)

class User(db.Model):

	__table_args__ = { 'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci' }

	id = db.Column(db.Integer, primary_key=True)

	def __str__(self):
		return str(self.id)

db.create_all()
#-------------------/database/---------------------------

#-------------------<tool functions>---------------------------
#decorator to check if user logged in
def is_logged(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if 'logged' in flask.session:
			return func(*args, **kwargs)
		else:
			return flask.redirect(flask.url_for("login"))
	return wrapper

@is_logged
def getUser():
	return Author.query.get(flask.session['user_id'])

#is user allowed to access this page
def user_allowed(level):
	if getUser().privileges <= level:
		return True
	else:
		return False
#------------------/tool functions/---------------------------

#--------------------<flask-admin>---------------------------
class AuthorView(ModelView):
	column_exclude_list = ['password',]
	form_excluded_columns = ['password',]

	def is_accessible(self):
		return user_allowed(2)

class ChannelView(ModelView):

	def is_accessible(self):
		return user_allowed(2)

class PostView(ModelView):

	def is_accessible(self):
		return user_allowed(5)

class UserView(ModelView):
	column_display_pk = True

	def is_accessible(self):
		return user_allowed(2)

class ButtonView(ModelView):
	column_display_pk = True

	def is_accessible(self):
		return user_allowed(2)


admin = Admin(app)
admin.add_view(AuthorView(Author, db.session))
admin.add_view(ChannelView(Channel, db.session))
admin.add_view(UserView(User, db.session))
admin.add_view(PostView(Post, db.session))
admin.add_view(ButtonView(Button, db.session))
#----------------------/flask-admin/-------------------------

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

#---------------------<author web pages>--------------------------
@app.route("/", methods=["GET","POST"])
@is_logged
def index():
	return flask.render_template("index.html", author = getUser())



@app.route("/new", methods=["GET","POST"])
@is_logged
def new_post():
	if flask.request.method == 'GET':
		return flask.render_template("new_post.html", author = getUser())
	else:
		f = flask.request.form.to_dict(flat=False)

		if flask.request.form['time_input'] == '':
			time = None
		else:
			time = dt.strptime(flask.request.form['time_input'], "%Y-%m-%d %H:%M")

		file = flask.request.files['image']

		new_post = Post(text = f["details"], image_addr = file.filename, channel_id = Channel.query.filter_by(name = f["channel"]).first().id, date = time)
		db.session.add(new_post)
		db.session.flush()

		if file and file.filename.endswith(('png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG')):
			file.save(os.path.join(config.UPLOAD_FOLDER, file.filename))

		for i in range(0, len(f['button_title'])):
			new_button = Button(text = f["button_title"][i], details = f["button_details"][i], post_id = new_post.id)
			db.session.add(new_button)
		db.session.commit()

		if not time:
			keyboard = telebot.types.InlineKeyboardMarkup()
			buttons = []
			for button in new_post.buttons:
				buttons.append(telebot.types.InlineKeyboardButton(text = button.text, callback_data = button.id))

			for i in range(0,len(buttons),config.buttons_row):
				keyboard.add(*buttons[i:i+config.buttons_row])

			try:
				if new_post.image_addr and new_post.text:
					photo = open(config.UPLOAD_FOLDER + new_post.image_addr, 'rb')
					bot.send_photo(new_post.channel.name, photo, new_post.text, reply_markup=keyboard)
					photo.close()
					os.remove(config.UPLOAD_FOLDER + new_post.image_addr)
				elif new_post.image_addr:
					photo = open(config.UPLOAD_FOLDER + new_post.image_addr, 'rb')
					bot.send_photo(new_post.channel.name, photo, reply_markup=keyboard)
					photo.close()
					os.remove(config.UPLOAD_FOLDER + new_post.image_addr)
				else:
					bot.send_message(new_post.channel.name, new_post.text, reply_markup=keyboard)

			except Exception as e:
				flask.flash(e)
				print(e)
		
		return flask.redirect(flask.url_for("new_post"))


@app.route('/cal') #page with calendar
@is_logged
def calendar():
	return flask.render_template("cal.html", author = getUser())

@app.route('/data') #send JSON events to calendar
@is_logged
def return_data():
	json = []
	posts = []
	for channel in Author.query.get(flask.session['user_id']).channel:
		for post in channel.posts:
			posts.append(post)
	for data in posts:
		json.append({"id":str(data.id),"title":str(data.text),"url":"/admin/post/edit/?id="+str(data.id),"start":str(data.date).replace(" ","T")})
	return flask.jsonify(json)
#---------------------/author web pages/--------------------------

#---------------------<telegram bot>--------------------------
@app.route('/{}'.format(config.secret), methods=["POST"])
def webhook():
	if flask.request.headers.get('content-type') == 'application/json':
		json_string = flask.request.get_data().decode('utf-8')
		update = telebot.types.Update.de_json(json_string)
		bot.process_new_updates([update])
		return ''
	else:
		flask.abort(403)

#bot start
@bot.message_handler(content_types=['photo', 'audio', 'sticker'])
def content_error(message):
	bot.send_message(message.chat.id, "Извините, я понимаю только текстовые сообщения и изображения, отправленные в виде файла")

@bot.callback_query_handler(func=lambda call: True)
def Callback_answer(call):
	try:
		start_time = time()
		button = Button.query.get(call.data)
		user = User.query.get(call.from_user.id)
		post = Post.query.get(button.post_id)

		if not user: #if user not in database. Create him
			user = User(id = call.from_user.id)
			db.session.add(user)
			db.session.flush()

		if user not in post.users: #if user not in post, add him in post and in button he pressed
			bot.answer_callback_query(call.id, show_alert=True, text=button.details + " Ответили также: " + str(button.users.len() / post.users.len() * 100) + "%")
			post.users.append(user)
			button.users.append(user)
			db.session.add(post)
			db.session.add(button)
			db.session.flush()
		else: #if user in post
			if user in button.users: #check if he's in button
				#if he's in button, then show him a message
				bot.answer_callback_query(call.id, show_alert=True, text=button.details)
			else: #if not - reject
				bot.answer_callback_query(call.id, text="Вы уже ответили")

		db.session.commit()
		end_time = time()
		print(end_time - start_time)

	except telebot.apihelper.ApiException:
		print(" Warning: Server overloaded and wasn't able to answer in time")
	#except Exception as e:
	#	print(" Callback Ошибка: " + str(e))
#---------------------/telegram bot/--------------------------