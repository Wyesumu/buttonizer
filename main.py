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

#-------------------<database>---------------------------

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
	channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=False)
	buttons = db.relationship('Button', backref='post', lazy=True)
	date = db.Column(db.DateTime)

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
#------------------/tool functions/---------------------------

#--------------------<flask-admin>---------------------------
class UserView(ModelView):
	column_exclude_list = ['password',]
	form_excluded_columns = ['password',]


admin = Admin(app)
admin.add_view(UserView(Author, db.session))
admin.add_view(UserView(User, db.session))
admin.add_view(UserView(Channel, db.session))
admin.add_view(UserView(Post, db.session))
admin.add_view(UserView(Button, db.session))
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
	return flask.render_template("index.html", author = Author.query.get(flask.session['user_id']))



@app.route("/new", methods=["GET","POST"])
@is_logged
def new_post():
	if flask.request.method == 'GET':
		return flask.render_template("new_post.html", author = Author.query.get(flask.session['user_id']))
	else:
		f = flask.request.form.to_dict(flat=False)

		if flask.request.form['time_input'] == '':
			time = None
		else:
			time = dt.strptime(flask.request.form['time_input'], "%Y-%m-%d %H:%M")

		new_post = Post(text = f["details"], image_addr = f["image"], channel_id = Channel.query.filter_by(name = f["channel"]).first().id, date = time)
		db.session.add(new_post)
		db.session.flush()

		if new_post.image_addr:
			if new_post.image_addr.endswith(('png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG')): # check if document is image
				file_info = bot.get_file(message.document.file_id) # download image
				downloaded_file = bot.download_file(file_info.file_path)
				src = config.UPLOAD_FOLDER + message.document.file_name;
				with open(src, 'wb') as new_file:
					new_file.write(downloaded_file) #put image to tmp folder

		for i in range(0, len(f['button_title'])):
			new_button = Button(text = f["button_title"][i], details = f["button_details"][i], post_id = new_post.id)
			db.session.add(new_button)
		db.session.commit()

		if not time:
			keyboard = telebot.types.InlineKeyboardMarkup()
			buttons = []
			for button in new_post.buttons:
				buttons.append(telebot.types.InlineKeyboardButton(text = button.text, callback_data = button.id))

			for i in range(0,len(buttons),3):
				print(*buttons[i:i+3])
				keyboard.add(*buttons[i:i+3])

			try:
				if new_post.image_addr and new_post.text:
					photo = open(config.tmp + PicAddr, 'rb')
					bot.send_photo(new_post.channel.name, photo, new_post.text, reply_markup=keyboard)
					photo.close()
					os.remove(config.UPLOAD_FOLDER + PicAddr)
				elif new_post.image_addr:
					photo = open(config.tmp + PicAddr, 'rb')
					bot.send_photo(new_post.channel.name, photo, reply_markup=keyboard)
					photo.close()
					os.remove(config.UPLOAD_FOLDER + PicAddr)
				else:
					bot.send_message(new_post.channel.name, new_post.text, reply_markup=keyboard)

			except Exception as e:
				flask.flash(e)
		
		return flask.redirect(flask.url_for("new_post"))


@app.route('/cal') #page with calendar
@is_logged
def calendar():
	return flask.render_template("cal.html", author = Author.query.get(flask.session['user_id']))

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
        if True: #need to make check if user in db
            #DbInsertUser(connection, call.data, call.from_user.id, call.from_user.username) #call.message.chat.username
            bot.answer_callback_query(call.id, show_alert=True, text=Button.query.get(call.data).details)
            print(call.id, call.data, Button.query.get(call.data))
        else:
            bot.answer_callback_query(call.id, text="Вы уже ответили")
    except telebot.apihelper.ApiException:
        print(" Warning: Server overloaded and wasn't able to answer in time")
    except Exception as e:
        print(" Callback Ошибка: " + str(e))
#---------------------/telegram bot/--------------------------