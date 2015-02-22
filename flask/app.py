# vim:fileencoding=utf8
#=====================================================================================================================
# 食べた！
#=====================================================================================================================

from flask import Flask, flash, request, redirect, render_template, session, url_for, send_file
import werkzeug
import rauth.service
import rauth.utils 
import os 
import logging 
import yaml
import sqlite3
import shutil
import datetime
import tempfile
import yaml
import PIL.Image

class FlaskWithHamlish(Flask):
    jinja_options = werkzeug.ImmutableDict(extensions = [
        'jinja2.ext.autoescape', 'jinja2.ext.with_', 'hamlish_jinja.HamlishExtension'
    ])

# Flask setup
app = FlaskWithHamlish(__name__)
# Setup logger
log = logging.getLogger(__name__)

class DB:
    DATABASE_PATH = None
    @classmethod
    def get(cls):
        con = sqlite3.connect(cls.DATABASE_PATH, isolation_level='DEFERRED')
        return con

    @classmethod
    def execute(cls, sql, params=[], cur=None):
        c = cur
        if cur:
            c = cur
        else:
            con = DB.get()
            c = con.cursor()
        c.execute(sql, params)
        r = c.fetchall()
        if not cur:
            con.close()
        return r

class Weight:
    @classmethod
    def update(cls, userid, day, weight, fatratio=None):
        con = DB.get()
        cur = con.cursor()
        weights = cls.get(userid, day, cur)
        params = []
        if weights:
            sql = 'update weights set weight = ?, fatratio = ?  where userid = ? and day = ?'
        else:
            sql = 'insert into weights (weight, fatratio, userid, day) values (?, ?, ?, ?)'
        params.extend((weight * 10, fatratio * 10 if fatratio else None, userid, day))
        cur.execute(sql, params)
        con.commit()
        con.close()
        return cls.get(userid, day)[0]
        
    @classmethod
    def get(cls, userid, day=None, cur=None):
        sql = 'select day, weight, fatratio from weights'
        params = ()
        if day:
            sql += ' where day = ?'
            params = (day,)
        sql += ' order by day desc'
        rows = DB.execute(sql, params, cur)
        weights = []
        for r in rows:
            weights.append({'userid': userid, 'day': r[0], 'weight': r[1]/10.0,
                'fatratio': r[2]/10.0 if r[2] else None})
        return weights 

class Photo:
    CURRENT_IMAGE_PATH = None
    @classmethod
    def add(cls, userid, date, make, model, gpsinfo, path):
        sql = 'insert into photos (userid, date, make, model, gpsinfo, path) values (?, ?, ?, ?, ?, ?)'
        params = (userid, date, make, model, yaml.dump(gpsinfo) if gpsinfo else None, 'dummy')
        con = DB.get()
        cur = con.cursor()
        cur.execute(sql, params)
        cur.execute('select last_insert_rowid()')
        id = cur.fetchone()[0]
        p = os.path.join(cls.CURRENT_IMAGE_PATH, '%d.%s' % (id, path.rsplit('.', 1)[1]))
        shutil.move(path, p)
        cur.execute('update photos set path = ? where id = ?', (p, id))
        con.commit()
        con.close()
        return cls.get(id=id)[0]

    @classmethod
    def get(cls, id=None, userid=None):
        sql = 'select id, userid, date, make, model, gpsinfo, path from photos'
        where = []
        params = []
        if id:
            where.append('id = ?')
            params.append(id)
        if userid:
            where.append('userid = ?')
            params.append(userid)
        if len(where) > 0:
            sql += ' where '
            for w in where:
                if len(sql) == len(' where '):
                    sql += ' and '
                sql += ' %s ' % w
        sql += ' order by date desc'
        rows = DB.execute(sql, params)
        photos = []
        for r in rows:
            photos.append({'id': r[0], 'userid': r[1], 'date': r[2], 'make': r[3], 'model': r[4],
                           'gpsinfo': yaml.load(r[5]) if r[5] else None, 'path': r[6]})
        return photos

class User:
    @classmethod
    def add(cls, screen_name, name, profile_image_url,
        access_token, access_token_secret, service='twitter'):
        con = DB.get()
        cur = con.cursor()
        user = cls.get(screen_name, cur=cur)
        if user:
            # TODO: DBを更新するように変更
            return user
        sql = '''
            insert into users (
                service, screen_name, name, profile_image_url,
                access_token, access_token_secret
            ) values (
                ?, ?, ?, ?, ?, ?
            )'''
        cur.execute(sql, (
            service, screen_name, name, profile_image_url,
            access_token, access_token_secret))
        con.commit()
        con.close()
        user = cls.get(screen_name)
        return user

    @classmethod
    def get(cls, screen_name, cur=None):
        sql = '''
            select
                id, service, name, profile_image_url,
                access_token, access_token_secret
            from users where screen_name = ?
        '''
        r = DB.execute(sql, params=(screen_name,), cur=cur)
        if len(r) == 0:

            log.debug('The user dose not exist. ' + screen_name)
            return None
        elif len(r) == 1:
            r = r[0]
            user = {
                'id': r[0], 'screen_name': screen_name, 'service': r[1], 'name': r[2],
                'profile_image_url': r[3], 'access_token': r[4], 
                'access_token_secret': r[5]}

        log.debug('user: %s' % str(user))
        return user


class Twitter:
    CONSUMER_KEY    = None
    CONSUMER_SECRET = None
    @classmethod
    def get_service(cls): 
        service = rauth.service.OAuth1Service(
            name='twitter',
            consumer_key=cls.CONSUMER_KEY,
            consumer_secret=cls.CONSUMER_SECRET,
            request_token_url='https://api.twitter.com/oauth/request_token',
            access_token_url='https://api.twitter.com/oauth/access_token',
            authorize_url='https://api.twitter.com/oauth/authorize',
            base_url='https://api.twitter.com/1.1/'
        )
        return service

#---------------------------------------------------------------------------------------------------------------------
# View
#---------------------------------------------------------------------------------------------------------------------

@app.route('/')
def index():
    if not 'user' in session:
        return render_template('signin.haml', data={'page_title': 'Sign in'})
    log.debug(session['user'])
    day = datetime.date.today().strftime('%Y-%m-%d')
    weights = Weight.get(session['user']['id'])
    weight = None
    fatratio = None
    for w in weights:
        # 当日登録済みの場合はそのデータを表示
        if w['day'] == day:
            weight = w['weight']
            fatratio = w['fatratio']
            break
        # 当日未登録の場合は直前の過去日のデータを表示
        elif w['day'] < day:
            weight = w['weight']
            fatratio = w['fatratio']
            break
    # 過去体重情報がなければ初期値
    if not weight:
        weight = 50
        fatratio = 15
    photos = Photo.get(userid=session['user']['id'])
    data={'today': day, 'weight': weight, 'fatratio': fatratio, 'weights': weights, 'photos': photos}
    return render_template('index.haml', data=data)
 
@app.route('/signin')
def signin():
    if 'signin' in session:
        return redirect(url_for('index'))
    twitter_service = Twitter.get_service()
    params = {'oauth_callback': url_for('callback', _external=True)}
    token = twitter_service.get_raw_request_token(params=params)
    data = rauth.utils.parse_utf8_qsl(token.content)
    session['request_token'] = (data['oauth_token'], data['oauth_token_secret'])
    return redirect(twitter_service.get_authorize_url(data['oauth_token'], **params))
 
@app.route('/callback')
def callback():
    if not 'request_token' in session:
        flash('システムエラー: Request token not found.', 'error')
        return redirect(url_for('index'))
    request_token, request_token_secret = session.pop('request_token')
 
    # check to make sure the user authorized the request
    if not 'oauth_token' in request.args:
        flash('システムエラー: You did not authorize the request.', 'error')
        return redirect(url_for('index'))
 
    try:
        twitter_service = Twitter.get_service()
        creds = {
            'request_token': request_token,
            'request_token_secret': request_token_secret}
        params = {'oauth_verifier': request.args['oauth_verifier']}
        twitter_session = twitter_service.get_auth_session(params=params, **creds)
    except Exception as ex:
        flash('Twitterでのサインインに問題が発生しました: ' + str(ex), 'error')
        return redirect(url_for('index'))

    verify = twitter_session.get(
        'account/verify_credentials.json', params={'format':'json'}).json()
    user = User.add(verify['screen_name'], verify['name'], verify['profile_image_url'],
        twitter_session.access_token, twitter_session.access_token_secret)
    log.debug(user)

    session.permanent = True
    session['user'] = {
        'id': str(user['id']),
        'screen_name': user['screen_name'],
        'profile_image_url': user['profile_image_url']
    }
    return redirect(url_for('index'))

@app.route('/photo/<id>')
def get_photo(id):
    photo = Photo.get(id=id)[0]
    
    return send_file(photo['path'])

@app.route('/regist/photo', methods=['POST'])
def regist_photo():
    f = request.files['photo']
    p = os.path.join(tempfile.mkdtemp(), 'image.' + f.filename.rsplit('.', 1)[1].lower())
    f.save(p)
    img = PIL.Image.open(p, 'r')
    exif = img._getexif()
    img.close()
    date = exif[36867] if 36867 in exif.keys() else \
           exif[36868] if 36868 in exif.keys() else \
           exif[306] if 306 in exif.keys() else None
    if date:
        date = datetime.datetime.strptime(date, '%Y:%m:%d %H:%M:%S')    
    else:
        date = datetime.datetime.now()
    date = date.strftime('%Y-%m-%d %H:%M:%S')
    make  = exif[271] if 271 in exif.keys() else None
    model = exif[272] if 272 in exif.keys() else None
    gpsinfo = exif[34853] if 34853 in exif.keys() else None

    photo = Photo.add(session['user']['id'], date, make, model, gpsinfo, p)
    log.debug(photo)
    flash('写真を登録しました。', 'info')
    return redirect(url_for('index'))

@app.route('/regist/weight')
def regist_weight():

    err = False
    # 不正なリクエストの判定
    if not 'day' in request.args.keys():
        flash('不正なリクエストです。[日付指定なし]', 'error')
        err = True
    if not 'weight' in request.args.keys():
        flash('不正なリクエストです。[体重指定なし]', 'error')
        err = True
    if not 'fatratio' in request.args.keys():
        flash('不正なリクエストです。[体脂肪指定なし]', 'error')
        err = True
    if err:
        return redirect(url_for('index'))
    # クエリー取得
    day = request.args.get('day')
    weight = request.args.get('weight')
    fatratio = request.args.get('fatratio')
    # 必須項目
    if not day:
        flash('日付が指定されていません。', 'error')
        err = True
    if not weight:
        flash('体重が指定されていません。', 'error')
        err = True
    if err:
        return redirect(url_for('index'))
    # フォーマットチェック&フォーマット正規化
    try:
        day = datetime.datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        flash('日付が不正なフォーマットです。', 'error')
        err = True
    try:
        weight = round(float(weight), 1)
    except ValueError:
        flash('体重を数値で指定してください。', 'error')
        err = True
    if fatratio:
        try:
            fatratio = round(float(fatratio), 1)
        except ValueError:
            flash('体脂肪率を数値で指定してください。', 'error')
            err = True
    if err:
        return redirect(url_for('index'))

    # 登録
    w = Weight.update(session['user']['id'], day, weight, fatratio)
    flash('%sの体重を登録しました。' % w['day'], 'info')
    return redirect(url_for('index'))

@app.route('/signout')
def signout():
    session.pop('user', None)
    return redirect(url_for('index'))



#---------------------------------------------------------------------------------------------------------------------
# Main
#---------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    with open(os.path.join(os.path.dirname(__file__), 'config.yaml')) as f:
        config = yaml.load(f)
    Twitter.CONSUMER_KEY = config['twitter']['consumer_key']
    Twitter.CONSUMER_SECRET = config['twitter']['consumer_secret']
    DB.DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'db', 'tabeta.sqlite3')
    app.jinja_env.hamlish_mode = 'debug'
    app.secret_key = config['secret_key']
    if config['current_image_path'][0] == '/':
        Photo.CURRENT_IMAGE_PATH = config['current_image_path']
    else:
        Photo.CURRENT_IMAGE_PATH = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), config['current_image_path'])
    logging.basicConfig(level=logging.DEBUG, format= \
        '%(asctime)s %(funcName)s@%(filename)s(%(lineno)d) [%(levelname)s] %(message)s')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.run(debug=True, host='0.0.0.0')
