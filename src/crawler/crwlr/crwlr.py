from multiprocessing import Event, Queue, Process, Lock, Manager
from random import choice
from unicodedata import name
from urllib.parse import urlparse, urlunparse, ParseResult
from logging import getLogger, basicConfig, DEBUG, ERROR, Filter, root as logging_root
import re
from itertools import starmap, chain
from collections import namedtuple
from queue import Empty as QEmpty
from dataclasses import dataclass
from enum import Enum
from time import sleep

import requests
from bs4 import BeautifulSoup as Bs

basicConfig(
    level=DEBUG,
    #level=ERROR
    format="[%(levelname)-8.8s]:\t[%(name)-10.10s]:%(funcName)-8.8s:%(lineno)4d:\t%(message)s"
)
log = getLogger(__name__)

modname = __name__

class CrwlrFilter(Filter):
    def filter(self, record):
        return record.name == modname

filter = CrwlrFilter()

for handler in logging_root.handlers:
        handler.addFilter(filter)


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

# TODO: add behavior to this class


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
    total_search_pages: int = 0
    completed_search_pages: int = 0
    total_products: int = 0
    completed_products:  int = 0
    base_url: str = ''


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
    #log.debug(f'Extracting page {page}')
    page_content = []
    document_tree = Bs(page.response.text, 'lxml')
    # TODO: complete definition here
    # TODO: refactor these conditions, look for an adequate design pattern
    if page.page_type == PageType.SEARCH_PAGE:
        #log.debug(f'Extracting search {page=}')
        page_number = document_tree.find(
            class_='andes-pagination__button andes-pagination__button--current')
        has_single_result_page = page_number is None
        if has_single_result_page:
            page_number = 1
        else:
            page_number = int(page_number.find(
                class_='andes-pagination__link').text)
        results_container: Bs = document_tree.find_all(
            class_='ui-search-results')[0]
        log.debug(f'Extracting from contianer {repr(results_container)[:100]}')
        item_containers = results_container.find_all(
            class_='ui-search-layout__item')
        log.debug(f'Item containers {len(item_containers)}')
        item_count = 0
        for item_container in item_containers:
            a = item_container.find(class_='ui-search-link')
            url = a.attrs['href']
            product_page = Page(
                page.base_url, url=url, page_type=PageType.PRODUCT_PAGE, page_number=page_number)
            page_content.append(product_page)
            item_count += 1
        log.debug(f'Extracted {item_count} products from search page')
        # a tag
        # FIXME: check when this is not present
        next_button = document_tree.find_all(
            class_='andes-pagination__link ui-search-link')
        next_button = next_button[1 if len(next_button) == 2 else 0]
        url = next_button.attrs['href']
        # TODO: avoid innecesary data duplication
        search_page = Page(base_url=page.base_url, url=url,
                           page_type=PageType.SEARCH_PAGE, page_number=page_number+1)
        page_content.append(
            search_page)
        return page_content
    elif page.page_type == PageType.PRODUCT_PAGE:
        #log.debug(f'Extracting product {page=}')
        pass


def fetcher(url_queue: Queue, response_queue: Queue, stop_ev: Event, category_fetch_completed: Event, q_timeout: float):
    while not stop_ev.is_set():
        #log.debug('Executing fetcher loop')
        try:
            #print(repr(q_timeout), type(q_timeout))
            page: Page = url_queue.get(timeout=q_timeout)
            log.debug(page)
        except QEmpty as ex:
            #log.debug('Continuing with next iteration')
            if category_fetch_completed.is_set():
                break
            continue
        #user_agent = choice(user_agents)
        user_agent = user_agents[2]  # we're chrome on win10
        headers = {
            "User-Agent": user_agent[1]
        }
        log.debug(f"Fetching url [{page.url}]")
        resp = requests.get(page.url, headers=headers)
        f_name = page.url.replace('/', '-').replace(':', '')
        question_mark = f_name.find('?')
        if question_mark >= 0:
            f_name = f_name[:question_mark]
        f = open(f'{f_name}.html', 'w')
        f.write(resp.text)
        f.close()
        if resp.status_code != 200:
            log.debug(f"Failed fetch of url [{page.url}]")
            url_queue.put(page)
            continue
        log.debug(f"Completed fetch of url [{page.url}]")
        page.response = resp
        response_queue.put(page)
    else:
        log.debug('Exitting fetcher loop')
        return


def save_product_info(*args, **kwargs):
    pass


def save_product_link(*args, **kwargs):
    pass


# TODO: improve function signature
def processor(response_queue: Queue, url_queue: Queue, q_timeout: float, stop_env: Event, category_status: dict, category_fetch_completed: Event, data_lock: Lock):
    product_count = 0
    while not stop_env.is_set():
        try:
            #print(repr(q_timeout))
            page: Page = response_queue.get(timeout=q_timeout)
        except QEmpty as ex:
            # log.debug(ex)
            # log.debug(type(ex))
            continue
        category: CategoryStatus = category_status[page.base_url]
        extracted_pages = extractor(page)
        #log.debug(f'{extracted_pages=}')
        if page.page_type == PageType.SEARCH_PAGE:
            print('Awaiting for data lock')
            data_lock.acquire()
            print('Data lock acquirred')
            i = 0
            for extracted_page in extracted_pages:
                if extracted_page.page_type == PageType.SEARCH_PAGE:
                    print(f'Current page number {page.page_number}, extracted page number {extracted_page.page_number}')
                if extracted_page.page_type == PageType.SEARCH_PAGE and extracted_page.page_number <= category.total_search_pages:
                    #print(f'Adding search page {extracted_page}')
                    #category.completed_search_pages += 1
                    url_queue.put(extracted_page)
                elif extracted_page.page_type == PageType.PRODUCT_PAGE:
                    save_product_link(extracted_page)
                    category.total_products += 1
                    log.debug(f'Adding product page {extracted_page}')
                    url_queue.put(extracted_page)
            category.completed_search_pages += 1
            category_status[page.base_url] = category
            print(f'SP {category_status}')
            data_lock.release()
        elif page.page_type == PageType.PRODUCT_PAGE:
            save_product_info(extracted_pages)
            data_lock.acquire()
            category.completed_products += 1
            category_status[page.base_url] = category
            data_lock.release()
        log.debug(f'{product_count=}')



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
        # log.debug(line)
        if not check_domain(url):
            raise ValueError(
                'Cannot find a valid url from allowed domains')
        categories.append(line.strip())
    f.close()
    return categories

def category_is_completed(category: CategoryStatus):
    return category.total_products == category.completed_products and category.total_search_pages == category.completed_search_pages

def start(categories, num_pages: int, num_procs: int, f_output: str, q_timeout, *args, **kwargs):
    print(f'Runnig with args {categories=}, {num_pages=}, {num_procs=}')
    mgr = Manager()
    categories = load_categories(categories)
    url_queue = Queue()
    response_queue = Queue()
    stop_ev = mgr.Event()
    category_fetch_completed = mgr.Event()
    fetchers = []
    processors = []
    category_status = mgr.dict()
    data_lock = mgr.Lock()
    for url in categories:
        page = Page(base_url=url, url=url,
                    page_type=PageType.SEARCH_PAGE, page_number=1)
        status = CategoryStatus(base_url=url, total_search_pages=num_pages)
        category_status[url] = status
        url_queue.put(page)
    for _ in range(num_procs):
        f = Process(target=fetcher, args=(
            url_queue, response_queue, stop_ev, category_fetch_completed, q_timeout))
        f.start()
        fetchers.append(f)
    for _ in range(num_procs):
        p = Process(target=processor, args=(response_queue, url_queue,
                    q_timeout, stop_ev, category_status, category_fetch_completed, data_lock))
        p.start()
        processors.append(p)
    while not stop_ev.is_set():
        sleep(5)
        data_lock.acquire()
        print(f'MP {category_status}')
        if all(category_is_completed(category) for category in category_status.values()):
            stop_ev.set()
        data_lock.release()
    for p in chain(fetchers, processors):
        p.join()
