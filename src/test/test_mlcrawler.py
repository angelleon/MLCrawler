import unittest
from multiprocessing import Queue, Event, Process
from time import sleep
from requests import Response

from crawler.crwlr import load_categories, fetcher

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

    # TODO: make this execution conditional as depends on infrastructure (network connection)
    # this sould be disabled for unit tests, enabled for itegration and accestance
    def test_fetcher(self):
        url = 'https://laptops.mercadolibre.com.mx/laptops-accesorios/#menu=categories'
        expected = Response
        url_queue = Queue()
        #url_queue.get(timeout=1)
        url_queue.put(url)
        response_queue = Queue()
        stop_ev = Event()
        p = Process(target=fetcher, args=(url_queue, response_queue, stop_ev))
        print('Starting fetcher process')
        p.start()
        print("Awaiting 20 seconds for fetcher")
        sleep(3)
        print('Stopping fetcher by event')
        stop_ev.set()
        sleep(2)
        print('Consuming output')
        resp = response_queue.get(timeout=1)
        if p.is_alive():
            print('Joining fetcher')
            p.join()
            print('Processes joint')
        else:
            print('Skipping join')
        actual = type(resp)
        self.assertEqual(actual, expected)
