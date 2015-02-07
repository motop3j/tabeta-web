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
        self.assertIsNone(None)

if __name__ == '__main__':
    unittest.main()

        
