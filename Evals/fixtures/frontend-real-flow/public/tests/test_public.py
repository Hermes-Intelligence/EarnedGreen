import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from panel import render_panel

class Tests(unittest.TestCase):
    def test_data_contains_item(self):
        self.assertIn("Ada", render_panel({"kind":"data","items":[{"name":"Ada"}]}))

if __name__ == "__main__": unittest.main()
