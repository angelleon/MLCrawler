import unittest

from crawler.crwlr import load_categories

class CrawlerTest(unittest.TestCase):
    def create_file(self, path: str, content: list[str]):
        with open(path, 'w') as f:
            f.writelines(content)

    def test_load_categories(self):
        content = ['http://mercadolibre.com.mx']
        expected = content[:]
        categories_path = 'test_categories.txt'
        self.create_file(categories_path, expected)
        actual = load_categories(categories_path)
        self.assertListEqual(expected, actual)
        content = ['badurl : // example . com', 'nourl dot com']
        self.create_file(categories_path, content)
        with self.assertRaises(ValueError):
            load_categories(categories_path)

