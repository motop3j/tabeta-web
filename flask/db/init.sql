create table users (
	id integer primary key autoincrement,
	service			text not null,
	screen_name		text not null,
	name 			text not null,
	profile_image_url	text not null,
	access_token		text not null,
	access_token_secret	text not null
);