# vim:fileencoding=utf8
#===================================================================================================
# 食べた！
#===================================================================================================

from flask import Flask, flash, request, redirect, render_template, session, url_for
from werkzeug import ImmutableDict
from rauth.service import OAuth1Service
from rauth.utils import parse_utf8_qsl
from datetime import datetime
import os 
import logging 
import yaml

class FlaskWithHamlish(Flask):
    jinja_options = ImmutableDict(extensions = [
        'jinja2.ext.autoescape', 'jinja2.ext.with_',
        'hamlish_jinja.HamlishExtension'
    ])


# Flask setup
app = FlaskWithHamlish(__name__)
# Setup logger
log = logging.getLogger(__name__)

class Twitter:
    CONSUMER_KEY = None
    CONSUMER_SECRET =None
    @classmethod
    def get_service(cls): 
        service = OAuth1Service(
            name='twitter',
            consumer_key=cls.CONSUMER_KEY,
            consumer_secret=cls.CONSUMER_SECRET,
            request_token_url='https://api.twitter.com/oauth/request_token',
            access_token_url='https://api.twitter.com/oauth/access_token',
            authorize_url='https://api.twitter.com/oauth/authorize',
            base_url='https://api.twitter.com/1.1/'
        )
        return service
# views
@app.route('/')
def index():
    if not 'user' in session:
        return render_template('signin.haml', data={'page_title': 'Sign in'})
    log.debug(session['user'])
    return render_template('index.haml', data={})
 
@app.route('/signin')
def signin():
    if 'signin' in session:
        return redirect(url_for('index'))
    twitter_service = Twitter.get_service()
    params = {'oauth_callback': url_for('callback', _external=True)}
    token = twitter_service.get_raw_request_token(params=params)
    data = parse_utf8_qsl(token.content)
    session['request_token'] = (data['oauth_token'], data['oauth_token_secret'])
    return redirect(twitter_service.get_authorize_url(data['oauth_token'], **params))
 
@app.route('/callback')
def callback():
    if not 'request_token' in session:
        flash('システムエラー: Request token not found.')
        return redirect(url_for('index'))
    request_token, request_token_secret = session.pop('request_token')
 
    # check to make sure the user authorized the request
    if not 'oauth_token' in request.args:
        flash('システムエラー: You did not authorize the request.')
        return redirect(url_for('index'))
 
    try:
        twitter_service = Twitter.get_service()
        creds = {'request_token': request_token, 'request_token_secret': request_token_secret}
        params = {'oauth_verifier': request.args['oauth_verifier']}
        twitter_session = twitter_service.get_auth_session(params=params, **creds)
    except Exception as ex:
        flash('Twitterでのサインインに問題が発生しました: ' + str(ex))
        return redirect(url_for('index'))

    log.debug(twitter_session.access_token)
    logging.debug(twitter_session.access_token_secret)

    # get user profile
    verify = twitter_session.get('account/verify_credentials.json', params={'format':'json'}).json()
    session['user'] = {
        'service': 'twitter',
        'name': verify['name'],
        'screen_name': verify['screen_name'],
        'profile_image_url': verify['profile_image_url']
    }

 
    return redirect(url_for('index'))
 
@app.route('/signout')
def signout():
    session.pop('user', None)
    return redirect(url_for('index'))
 
if __name__ == '__main__':
    with open(os.path.join(os.path.dirname(__file__), 'config.yaml')) as f:
        config = yaml.load(f)
    Twitter.CONSUMER_KEY = config['twitter']['consumer_key']
    Twitter.CONSUMER_SECRET = config['twitter']['consumer_secret']
    app.jinja_env.hamlish_mode = 'debug'
    app.secret_key = config['secret_key']
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(funcName)s@%(filename)s(%(lineno)d) [%(levelname)s] %(message)s')
    app.run(debug=True)
