# vim:fileencoding=utf8
#===========================================================================================
# app.Wight クラスのテスト
#===========================================================================================

import unittest
import common
import os
import shutil
import imp

class WeightTest(unittest.TestCase):

    def setUp(self):
        common.init_test_env(self, os.path.basename(__file__))

    def test_get(self):
        u = self.app.User.get('hoge')
        self.assertIsNone(u)
        u = self.app.User.add('hoge', 'ほげ', 'http://twitter/hoge.jpg', 'token', 'secret')
        self.assertIsNotNone(u)
        self.assertEqual(u['id'], 1)
        self.assertEqual(u['service'], 'twitter')
        self.assertEqual(u['screen_name'], 'hoge')
        self.assertEqual(u['name'], 'ほげ')
        self.assertEqual(u['profile_image_url'], 'http://twitter/hoge.jpg')
        self.assertEqual(u['access_token'], 'token')
        self.assertEqual(u['access_token_secret'], 'secret')
        self.assertEqual(len(u), 7)



if __name__ == '__main__':
    unittest.main()

        
