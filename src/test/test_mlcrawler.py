import unittest

from crawler.crwlr import load_categories

class CrawlerTest(unittest.TestCase):
    def test_load_categories(self):
        expected = ['']
        categories_path = 'test_categories.txt'
        with open(categories_path, 'w') as f:
            f.writelines(expected)
        actual = load_categories(categories_path)
        self.assertListEqual(expected, actual)