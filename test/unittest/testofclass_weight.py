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

    def test_add(self):
        w = self.app.Weight.update(1, '2000-01-01', 80.5)
        self.assertEqual(w['userid'], 1)
        self.assertEqual(w['day'], '2000-01-01')
        self.assertEqual(w['weight'], 80.5)
        self.assertIsNone(w['fatratio'])
        w = self.app.Weight.update(1, '2000-01-02', 80.5, 30.1)
        self.assertEqual(w['userid'], 1)
        self.assertEqual(w['day'], '2000-01-02')
        self.assertEqual(w['weight'], 80.5)
        self.assertEqual(w['fatratio'], 30.1)
        w = self.app.Weight.update(1, '2000-01-02', 79.5)
        self.assertEqual(w['userid'], 1)
        self.assertEqual(w['day'], '2000-01-02')
        self.assertEqual(w['weight'], 79.5)
        self.assertIsNone(w['fatratio'], None)

    def test_get(self):
        w = self.app.Weight.get(1)
        self.assertEqual(len(w), 0)
        self.app.Weight.update(1, '2000-01-01', 80.1)
        self.app.Weight.update(1, '2000-01-02', 80.2)
        self.app.Weight.update(1, '2000-01-03', 80.3)
        self.app.Weight.update(1, '2000-01-04', 80.4)
        w = self.app.Weight.get(1)
        self.assertEqual(w[0]['day'], '2000-01-01')
        self.assertEqual(w[1]['day'], '2000-01-02')
        self.assertEqual(w[2]['day'], '2000-01-03')
        self.assertEqual(w[3]['day'], '2000-01-04')
if __name__ == '__main__':
    unittest.main()

        
