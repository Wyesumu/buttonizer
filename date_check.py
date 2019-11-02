from time import sleep
from datetime import datetime as dt
from main import Post, send_message

while True:
	for post in Post.query.filter_by(date = dt.now()).all():
		send_message(post)
	sleep(60)