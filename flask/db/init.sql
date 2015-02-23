create table users (
    id          integer primary key autoincrement,
    service     text not null,
    screen_name text not null,
    name        text not null,
    profile_image_url   text not null,
    access_token        text not null,
    access_token_secret text not null
);

create table weights (
    userid      integer not null,
    day         text not null,
    weight      integer not null,
    fatratio    integer,
    primary key (userid, day)
);

create table photos (
    id          integer primary key autoincrement,
    userid      integer not null,
    date        text not null,
    make        text,
    model       text,
    gpsinfo     text,
    path        text not null,
    thumbnail   text not null
);
   

