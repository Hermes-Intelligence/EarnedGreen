import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'));from service import process_order
class T(unittest.TestCase):
 def test_happy(self):self.assertEqual(process_order({'id':'1'})['status'],'processed')
if __name__=='__main__':unittest.main()
