from multiprocessing import Event, Queue, Process
from random import choice
from unicodedata import name
from urllib.parse import urlparse, urlunparse, ParseResult
from logging import getLogger, basicConfig, DEBUG, ERROR
import re
from itertools import starmap, chain
from collections import namedtuple
from queue import Empty as QEmpty
from dataclasses import dataclass
from enum import Enum

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


class PageType(Enum):
    SEARCH_PAGE = 1
    PRODUCT_PAGE = 2


@dataclass
class Page:
    base_url: str = ''
    url: str = ''
    page_type: PageType = PageType.SEARCH_PAGE
    page_number: int = 1
    response: requests.Response = None


@dataclass
class CategoryStatus:
    completed: bool = False
    total_products: int = 0
    total_pages: int = 0


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
def extractor(page: Page) -> list[Page]:
    print(f'Extracting page {page}')
    page_content = []
    document_tree = Bs(page.response.text, 'lxml')
    # TODO: complete definition here
    # TODO: refactor these condition
    if page.page_type == PageType.SEARCH_PAGE:
        print(f'Processing search page {page}')
        page_number = document_tree.find(
            class_='andes-pagination__button andes-pagination__button--current')
        has_sigle_result_page = page_number is None
        if has_sigle_result_page:
            page_number = 1
        else:
            page_number = int(page_number.find(
                class_='andes-pagination__link').text)
        if page_number > max_pages:
            return
        results_container = document_tree.find_all(class_='ui-search-results')[0]
        for item_container in results_container.find_all('ui-search-layout__item'):
            print(f'Processing item contianer {item_container}')
            a = item_container.find(class_='ui-search-link')
            url = a.attrs['href']
            product_page = Page(page.base_url, url=url, page_type=PageType.PRODUCT_PAGE, page_number=page_number)
            page_content.append(product_page)
        # a tag
        # FIXME: check when this is not present
        next_button = document_tree.find_all(
            class_='andes-pagination__link ui-search-link')
        next_button = next_button[1 if len(next_button) == 2 else 0]
        url = next_button.attrs['href']
        # TODO: avoid innecesary data duplication
        search_page = Page(base_url=page.base_url, url=url, page_type=PageType.SEARCH_PAGE, page_number=page_number+1)
        page_content.append(
            search_page)
        return page_content
    elif page.page_type == PageType.PRODUCT_PAGE:
        print(f'Extracting product {page=}')


def fetcher(url_queue: Queue, response_queue: Queue, stop_ev: Event, category_fetch_completed: Event):
    while not stop_ev.is_set():
        #print('Executing fetcher loop')
        try:
            page: Page = url_queue.get(timeout=1)
            print(page)
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
        print(f"Fetching url [{page.url}]")
        resp = requests.get(page.url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed fetch of url [{page.url}]")
            url_queue.put(page)
            continue
        print(f"Completed fetch of url [{page.url}]")
        page.response = resp
        response_queue.put(page)
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
            page: Page = response_queue.get(timeout=timeout)
        except QEmpty as ex:
            # print(ex)
            # print(type(ex))
            continue
        # TODO: improve method signature (maybe using dict expansion)
        extracted_pages = extractor(page)
        if extracted_pages is None:
            category_status[page.base_url]['category_fetch_completed'] = True
            if all(category_status[k]['category_fetch_completed'] for k in category_status):
                category_fetch_completed.set()
            continue
        print(f'{extracted_pages=}')
        if page.page_type == PageType.SEARCH_PAGE:
            for extracted_page in extracted_pages:
                if extracted_page.page_type == PageType.SEARCH_PAGE:
                    #print(f'Adding search page {extracted_page}')
                    #url_queue.put(extracted_page)
                    continue
                save_product_link(extracted_page)
                print(f'Adding product page {extracted_page}')
                url_queue.put(extracted_page)
        else:
            save_product_info(extracted_pages)


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


def start(categories, num_pages: int, num_procs: int, *args, **kwargs):
    print(f'Runnig with args {categories=}, {num_pages=}, {num_procs=}')
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
        page = Page(base_url=url, url=url,
                    page_type=PageType.SEARCH_PAGE, page_number=1)
        url_queue.put(page)
    for _ in range(num_procs):
        f = Process(target=fetcher, args=(
            url_queue, response_queue, stop_ev, category_fetch_completed))
        f.start()
        fetchers.append(f)
    for _ in range(num_procs):
        p = Process(target=processor, args=(response_queue, url_queue,
                    1, stop_ev, category_status, category_fetch_completed))
        p.start()
        processors.append(p)
    for p in chain(fetchers, processors):
        p.join()
