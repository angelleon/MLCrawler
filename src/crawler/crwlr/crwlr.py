from multiprocessing import Event, Queue, Process
from random import choice
from unicodedata import name
from urllib.parse import urlparse, urlunparse, ParseResult
from logging import getLogger, basicConfig, DEBUG, ERROR
import re
from itertools import starmap, chain
from collections import namedtuple
from queue import Empty as QEmpty

import requests
from bs4 import BeautifulSoup as Bs

basicConfig(level=ERROR)
log = getLogger(__name__)

items_per_page = 48
pages = 10

max_pages = 10

fetchers_number = 1
processors_number = 1

# TODO: make this configurable for arbitrary web crawler
allowed_domains = ['mercadolibre.com.mx']

domain_regexps = [re.compile(f'\\w*\\.{domain}') for domain in allowed_domains]

UserAgent = namedtuple('UserAgent', ['browser', 'version', 'os', 'user_agent'])
FetchResponse = namedtuple("FetchResponse", ["page_number", "response"])
Url = namedtuple("Url", ['page_number', 'url'])
ResultPage = namedtuple(
    "ResultPage", ['base_url', 'page_number', 'url'])


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

SEARCH_PAGE = 0
PRODUCT_PAGE = 1


# TODO: improve error handling
# TODO: avoid passing unnecesary arguments, maybe use dict expansion
def extractor(url_type: int, resp: requests.Response, base_url) -> dict:
    page_content = []
    page = Bs(resp.content, 'lxml')
    # TODO: complete definition here
    # TODO: refactor these condition
    if url_type == SEARCH_PAGE:
        page_number = page.find(
            class_='andes-pagination__button andes-pagination__button--current')
        has_sigle_result_page = page_number is None
        if has_sigle_result_page:
            page_number = 1
        else:
            page_number = int(page_number.find(
                class_='andes-pagination__link').text)
        if page_number > max_pages:
            return
        results_container = page.find_all(class_='ui-search-results')[0]
        for item_container in results_container.find_all('ui-search-layout__item'):
            a = item_container.find(class_='ui-search-link')
            link = a.attrs['href']
            page_content.append({'url_type': PRODUCT_PAGE, 'url': link})
        # a tag
        # FIXME: check when this is not present
        next_button = page.find_all(
            class_='andes-pagination__link ui-search-link')
        next_button = next_button[1 if len(next_button) == 2 else 0]
        link = next_button.attrs['href']
        print(f'Adding search page {link}')
        # TODO: avoid innecesary data duplication
        page_content.append({'url_type': SEARCH_PAGE, 'url': link, 'base_url': base_url})
        return page_content
    elif url_type == PRODUCT_PAGE:
        pass


def fetcher(url_queue: Queue, response_queue: Queue, stop_ev: Event, category_fetch_completed: Event):
    while not stop_ev.is_set():
        #print('Executing fetcher loop')
        try:
            url_info = url_queue.get(timeout=1)
            print(url_info)
            url_type = url_info['url_type']
            url = url_info['url']
            base_url = url_info['base_url']
        except QEmpty as ex:
            #print('Continuing with next iteration')
            if category_fetch_completed.is_set():
                break
            continue
        #user_agent = choice(user_agents)
        user_agent = user_agents[2]  # we're chrome on win10
        headers = {
            "User-Agent": user_agent[1]
        }
        #print(f"Fetching url [{url}]")
        resp = requests.get(url, headers=headers)
        print(f"Completed fetch of url [{url}]")
        response_queue.put({'url_type': url_type, 'content': resp, 'base_url': base_url})
    else:
        #print('Exitting fetcher loop')
        return


def save_product_info(*args, **kwargs):
    pass


def save_product_link(*args, **kwargs):
    pass


# TODO: improve function signature
def processor(response_queue: Queue, url_queue: Queue, timeout: int, stop_env: Event, category_status: dict, category_fetch_completed: Event):
    while not stop_env.is_set():
        try:
            resp = response_queue.get(timeout=timeout)
        except QEmpty as ex:
            # print(ex)
            # print(type(ex))
            continue
        # TODO: improve method signature (maybe using dict expansion)
        page_info = extractor(resp['url_type'], resp['content'], resp['base_url'])
        base_url = resp['base_url']
        if page_info is None:
            category_status[base_url]['category_fetch_completed'] = True
            if all(category_status[k]['category_fetch_completed'] for k in category_status):
                category_fetch_completed.set()
            continue
        if resp['url_type'] == SEARCH_PAGE:
            for info in page_info:
                if info['url_type'] == SEARCH_PAGE:
                    url_queue.put(info)
                    continue
                save_product_link(info)
                url_queue.put(info)
        else:
            save_product_info(page_info)


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
        # print(line)
        if not check_domain(url):
            raise ValueError(
                'Cannot find a valid url from allowed domains')
        categories.append(line.strip())
    f.close()
    return categories


def start(categories, *args, **kwargs):
    categories = load_categories(categories)
    url_queue = Queue()
    response_queue = Queue()
    stop_ev = Event()
    category_fetch_completed = Event()
    category_status = {k: {'category_fetch_completed': False}
                       for k in categories}
    fetchers = []
    processors = []
    for url in categories:
        url_queue.put({'url_type': SEARCH_PAGE, 'url': url, 'base_url': url})
    for _ in range(fetchers_number):
        f = Process(target=fetcher, args=(
            url_queue, response_queue, stop_ev, category_fetch_completed))
        f.start()
        fetchers.append(f)
    for _ in range(processors_number):
        p = Process(target=processor, args=(response_queue, url_queue,
                    1, stop_ev, category_status, category_fetch_completed))
        p.start()
        processors.append(p)
    for p in chain(fetchers, processors):
        p.join()
