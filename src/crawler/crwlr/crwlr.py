from multiprocessing import Event, Queue, Process
from random import choice
from unicodedata import name
from urllib.parse import urlparse, urlunparse, ParseResult
from logging import getLogger, basicConfig, DEBUG
import re
from itertools import starmap, chain
from collections import namedtuple
from queue import Empty as QEmpty

import requests

basicConfig(level=DEBUG)
log = getLogger(__name__)

items_per_page = 48
pages = 10

fetchers_number = 5
processors_number = 5

# TODO: make this configurable for arbitrary web crawler
allowed_domains = ['mercadolibre.com.mx']

domain_regexps = [re.compile(f'\\w*\\.{domain}') for domain in allowed_domains]

UserAgent = namedtuple('UserAgent', ['browser', 'version', 'os', 'user_agent'])
FetchResponse = namedtuple("FetchResponse", ["page_number", "response"])
Url = namedtuple("Url", ['page_number', 'url'])
ResultPage = namedtuple("ResultPage", ['base_url', 'products_per_page', 'page_number', 'url'])


"""https://developers.whatismybrowser.com/useragents/explore/"""
user_agents = (
    UserAgent("Edge",     "98", "Win10",
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36 Edg/98.0.1108.43"),
    UserAgent("Safari",     "15.4", "MacOS",
              "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15"),
    UserAgent("Chrome",     "97", "Win10",
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"),
    UserAgent("Safari",     "15.4", "iPhone",
              "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1"),
    UserAgent("Firefox",    "100", "Win10",
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0"),
    UserAgent("Chrome",     "101", "Android",
              "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Mobile Safari/537.36"),
    UserAgent("Google bot", "2.1", "",
              "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
)


def extractor(resp: requests.Response) -> tuple[str, float, str]:
    raise NotImplementedError


def fetcher(url_queue: Queue, response_queue: Queue, stop_ev: Event):
    while not stop_ev.is_set():
        print('Executing fetcher loop')
        try:
            url = url_queue.get(timeout=1)
        except QEmpty as ex:
            print('Continuing with next iteration')
            continue
        #user_agent = choice(user_agents)
        user_agent = user_agents[2] # we're chrome on win10
        headers = {
            "User-Agent": user_agent[1]
        }
        print(f"Fetching url [{url}]")
        resp = requests.get(url, headers=headers)
        print(f"Completed fetch of url [{url}]")
        response_queue.put(resp)
    else:
        print('Exitting fetcher loop')
        return


def save(*args, **kwargs):
    pass


def processor(response_queue: Queue, generator_queue: Queue, timeout: int, stop_env: Event):
    while not stop_env.is_set():
        try:
            resp = response_queue.get(timeout=timeout)
        except QEmpty as ex:
            print(ex)
            print(type(ex))
            continue
        products, prices, url, page_number = extractor(resp)
        if page_number == 1:
            generator_queue.put(ResultPage(url, len(products), 1, url))
        save(products, prices, url)


def check_domain(url: ParseResult):
    return all(
        starmap(
            lambda domain, regex: url.netloc.endswith(
                domain) or regex.search(url.path) is not None,
            zip(
                allowed_domains,
                domain_regexps)))


def load_categories(path: str) -> list[str]:
    categories = []
    f = open(path)
    for line in f.readlines():
        url = urlparse(line)
        line = urlunparse(url[:3] + ('', '', ''))
        print(line)
        if not check_domain(url):
            raise ValueError(
                'Cannot find a valid url from allowed domains')
        categories.append(line.strip())
    f.close()
    return categories


def gen_urls(category_number: int, generator_queue: Queue, stop_env: Event):
    i = 0
    while not stop_env.is_set() or i >= category_number:
        if (url := generator_queue.get(timeout=1)) is None:
            continue
        i += 1


def start(categories, *args, **kwargs):
    categories = load_categories(categories)
    url_queue = Queue()
    response_queue = Queue()
    stop_ev = Event()
    fetchers = []
    processors = []
    for url in categories:
        url_queue.put(Url(0, url))
    for _ in range(fetchers_number):
        f = Process(target=fetcher, args=(url_queue, response_queue, stop_ev))
        f.start()
        fetchers.append(f)
    for _ in range(processors_number):
        p = Process(target=processor)
        p.start()
        processors.append(p)
    generator = Process(target=gen_urls)
    generator.start()
    generator.join()
    for p in chain(fetchers, processors):
        p.join()
