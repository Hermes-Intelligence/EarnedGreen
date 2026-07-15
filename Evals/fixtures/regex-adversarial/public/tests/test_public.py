import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"src"));from extractor import extract_records
class T(unittest.TestCase):
 def test_basic(self): self.assertEqual(extract_records("name: Ada\nrole: admin"),[{"name":"name","value":"Ada"},{"name":"role","value":"admin"}])
if __name__=='__main__':unittest.main()
