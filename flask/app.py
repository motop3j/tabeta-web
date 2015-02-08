# vim:fileencoding=utf8
#===========================================================================================
# 食べた！
#===========================================================================================

from flask import Flask, flash, request, redirect, render_template, session, url_for
import werkzeug
import rauth.service
import rauth.utils 
import os 
import logging 
import yaml
import sqlite3
import datetime
import tempfile

class FlaskWithHamlish(Flask):
    jinja_options = werkzeug.ImmutableDict(extensions = [
        'jinja2.ext.autoescape', 'jinja2.ext.with_',
        'hamlish_jinja.HamlishExtension'
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
    def update(cls, id, day, weight, fatratio=None):
        con = DB.get()
        cur = con.cursor()
        weights = cls.get(id, day, cur)
        params = []
        if weights:
            sql = '''
                update weights set weight = ?, fatratio = ?
                where userid = ? and day = ?
            '''
        else:
            sql = 'insert into weights (weight, fatratio, userid, day) values (?, ?, ?, ?)'
        params.extend((weight * 10, fatratio * 10 if fatratio else None, id, day))
        cur.execute(sql, params)
        con.commit()
        con.close()
        return cls.get(id, day)[0]
        
    @classmethod
    def get(cls, id, day=None, cur=None):
        sql = 'select day, weight, fatratio from weights'
        params = ()
        if day:
            sql += ' where day = ?'
            params = (day,)
        sql += ' order by day desc'
        rows = DB.execute(sql, params, cur)
        weights = []
        for r in rows:
            weights.append({'userid': id, 'day': r[0], 'weight': r[1]/10.0,
                'fatratio': r[2]/10.0 if r[2] else None})
        return weights 

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

#-------------------------------------------------------------------------------------------
# View
#-------------------------------------------------------------------------------------------

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
        
    data={'today': day, 'weight': weight, 'fatratio': fatratio, 'weights': weights}
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

@app.route('/regist/photo', methods=['POST'])
def regist_photo():
    log.debug(request.files)
    f = request.files['photo']
    log.debug(f)
    p = os.path.join(tempfile.mkdtemp(), 'image.' + f.filename.rsplit('.', 1)[1])
    f.save(p)
    log.debug(p)

    return ""

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



#-------------------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------------------

if __name__ == '__main__':
    with open(os.path.join(os.path.dirname(__file__), 'config.yaml')) as f:
        config = yaml.load(f)
    Twitter.CONSUMER_KEY = config['twitter']['consumer_key']
    Twitter.CONSUMER_SECRET = config['twitter']['consumer_secret']
    DB.DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'db', 'tabeta.sqlite3')
    app.jinja_env.hamlish_mode = 'debug'
    app.secret_key = config['secret_key']
    logging.basicConfig(level=logging.DEBUG, format= \
        '%(asctime)s %(funcName)s@%(filename)s(%(lineno)d) [%(levelname)s] %(message)s')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.run(debug=True, host='0.0.0.0')
