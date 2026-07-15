import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'));from pricing import calculate_total
class T(unittest.TestCase):
 def test_old(self):self.assertEqual(calculate_total([10,20],.1),33)
if __name__=='__main__':unittest.main()
