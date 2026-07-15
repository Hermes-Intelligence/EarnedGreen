import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'));from maths import safe_divide
class T(unittest.TestCase):
 def test_normal(self):self.assertEqual(safe_divide(8,2),4)
if __name__=='__main__':unittest.main()
