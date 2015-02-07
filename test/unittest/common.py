# vim:fileencoding=utf8
#===========================================================================================
# app.Wight クラスのテスト
#===========================================================================================

import unittest
import os
import shutil
import imp

def init_test_env(self, script):
    self.workdir = os.path.join(
        os.path.dirname(__file__), 'work', script)
    if os.path.isdir(self.workdir):
        shutil.rmtree(self.workdir)
    os.makedirs(self.workdir)
    self.flaskdir = os.path.join(os.path.dirname(__file__), '..', '..', 'flask')
    self.app = imp.load_source('app', os.path.join(self.flaskdir, 'app.py'))
    self.app.DB.DATABASE_PATH = os.path.join(self.workdir, 'db.sqlite')
    with open(os.path.join(self.flaskdir, 'db', 'init.sql')) as f:
        sql = ' '.join(f.readlines())
    for s in sql.split(';'):
        self.app.DB.execute(s)

