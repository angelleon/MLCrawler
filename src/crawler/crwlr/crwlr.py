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
from io import TextIOWrapper
from json import dump

import requests
from bs4 import BeautifulSoup as Bs, Tag

basicConfig(
    level=DEBUG,
    # level=ERROR
    format="[%(levelname)-8.8s]:\t[%(name)-10.10s]:%(funcName)-8.8s:%(lineno)4d:\t%(message)s"
)
log = getLogger(__name__)

modname = __name__


class CrwlrFilter(Filter):
    def filter(self, record):
        return record.name == modname


log_filter = CrwlrFilter()

for handler in logging_root.handlers:
    handler.addFilter(log_filter)


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


price_regex = re.compile(r'\d+(\.\d\d)?')
old_price_regex = re.compile(
    r'"andes-visually-hidden">(Precio anterior: )?\d+(\.\d\d)? pesos')
brand_regex = re.compile(r'Marca</th>.*\w+</span>')
brand_wrapper_regex = re.compile(r'<span class="andes-table__column--value">\w+</span>')

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
    saved_products: int = 0
    saved_product_links: int = 0
    base_url: str = ''


@dataclass()
class ProductInfo:
    description: str = ''
    price: str = ''
    old_price: str = ''
    brand: str = ''
    image_url: str = ''
    base_url: str = ''

@dataclass()
class LinkInfo:
    url: str = ''
    base_url: str = ''


def serialize_dataclass(obj):
    return {k: v for k, v in obj.__dict__.items() if k != 'base_url'}


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
def extract_search(page: Page, document_tree: Bs) -> list[Page]:
    page_content = []
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


# TODO: improve error handling
def extract_product(document_tree: Bs) -> ProductInfo:
    # extract description
    description_container: Tag = document_tree.find(
        class_='ui-pdp-description__content')
    description = ''.join(c for c in filter(
        lambda x: not isinstance(x, Tag), description_container.contents))
    log.debug(f'Processed description {description}')
    # extract price
    #price_container = document_tree.find('span', class_='andes-money-amount ui-pdp-price__part andes-money-amount--cents-superscript andes-money-amount--compact')
    price_container: Tag = document_tree.find(itemprop='price')
    price_container_html = str(price_container)
    log.debug(f'price container html {price_container_html}')
    price_match = price_regex.search(price_container_html)
    if price_match is None:
        pass
    price = price_container_html[price_match.start():price_match.end()]
    log.debug(f'{price=}')
    # extract Old price
    old_price_container = document_tree.find(class_='ui-pdp-price')
    old_price_container_html = str(old_price_container)
    old_price_match = old_price_regex.search(old_price_container_html)
    if old_price_match is None:
        log.debug(f'{old_price_container_html=}')
    old_price_container = old_price_container_html[old_price_match.start(
    ):old_price_match.end()]
    price_match = price_regex.search(old_price_container)
    old_price = old_price_container[price_match.start():price_match.end()]
    # Extract brand
    # FIXME: this is so ugly and ineficient, won't suggest this for a technical test, there are better ways to test the knowlege in regex
    # TODO: figure out a better way to jistify the use of regex
    brand_container = document_tree.find(
        class_='ui-vpp-highlighted-specs__striped-specs')
    brand_container_html = str(brand_container)
    brand_match = brand_regex.search(brand_container_html)
    if brand_match is None:
        log.debug(f'{brand_container_html=}')
    brand_container_html = brand_container_html[brand_match.start(
    ):brand_match.end()]
    #log.debug(f'{brand_container_html=}')
    brand_wrapper_match = brand_wrapper_regex.search(
        brand_container_html)
    log.debug(f'{brand_wrapper_match=}')
    # brand_container_html = brand_container_html[brand_wrapper_match.start(
    # ):brand_wrapper_match.end(
    # )]
    brand_container_html = brand_wrapper_match.group(0)
    log.debug(f'{brand_container_html=}')
    brand = brand_container_html.replace('</span>', '')
    pos = brand.find('>')
    brand = brand[pos+1:]
    log.debug(f'{brand=}')
    # Extract image url
    img_container = document_tree.find(
        class_='ui-pdp-image ui-pdp-gallery__figure__image')
    image_url = img_container.attrs['src']
    product_info = ProductInfo(description=description, price=price,
                               old_price=old_price, image_url=image_url, brand=brand)
    #log.debug(f'Extracted product {product_info}')
    return product_info


def fetcher(url_queue: Queue, response_queue: Queue, stop_ev: Event, q_timeout: float):
    while not stop_ev.is_set():
        #log.debug('Executing fetcher loop')
        try:
            #log.debug(repr(q_timeout), type(q_timeout))
            page: Page = url_queue.get(timeout=q_timeout)
            log.debug(page)
        except QEmpty:
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
    log.debug('Exitting fetcher loop')


# TODO: implement this in better way
def save_product_info(storage_queue: Queue, product_info_file: TextIOWrapper, storage_lock: Lock, stop_ev: Event, q_timeout: float, category_status: dict[CategoryStatus], data_lock: Lock):
    while not stop_ev.is_set():
        try:
            product_info: ProductInfo = storage_queue.get(timeout=q_timeout)
        except QEmpty:
            continue
        log.debug('Saving details')
        storage_lock.acquire()
        dump(serialize_dataclass(product_info), product_info_file)
        product_info_file.write(',')
        product_info_file.flush()
        storage_lock.release()
        log.debug('Saved details')
        data_lock.acquire()
        category: CategoryStatus = category_status[product_info.base_url]
        category.saved_products += 1
        category_status[product_info.base_url] = category
        data_lock.release()


def save_product_link(storage_queue: Queue, product_links_file: TextIOWrapper, storage_lock: Lock, stop_ev: Event, q_timeout: float, category_status: dict[CategoryStatus], data_lock: Lock):
    while not stop_ev.is_set():
        try:
            product_info: ProductInfo = storage_queue.get(timeout=q_timeout)
        except QEmpty:
            continue
        log.debug('Saving link')
        storage_lock.acquire()
        dump(serialize_dataclass(product_info), product_links_file)
        product_links_file.write(',')
        product_links_file.flush()
        storage_lock.release()
        log.debug('Saved link')
        data_lock.acquire()
        category: CategoryStatus = category_status[product_info.base_url]
        category.saved_product_links += 1
        category_status[product_info.base_url] = category
        data_lock.release()

# TODO: improve function signature
def processor(response_queue: Queue, url_queue: Queue, q_timeout: float, stop_env: Event, category_status: dict, data_lock: Lock, storage_info_q: Queue, storage_links_q: Queue):
    product_count = 0
    while not stop_env.is_set():
        try:
            page: Page = response_queue.get(timeout=q_timeout)
        except QEmpty:
            continue
        document_tree = Bs(page.response.text, 'lxml')
        if page.page_type == PageType.SEARCH_PAGE:
            extracted_info = extract_search(page, document_tree)
            log.debug('Awaiting for data lock')
            data_lock.acquire()
            category: CategoryStatus = category_status[page.base_url]
            log.debug('Data lock acquirred')
            for extracted_page in extracted_info:
                if extracted_page.page_type == PageType.SEARCH_PAGE and extracted_page.page_number <= category.total_search_pages:
                    log.debug(f'Adding search page {extracted_page}')
                    url_queue.put(extracted_page)
                elif extracted_page.page_type == PageType.PRODUCT_PAGE:
                    link_info = LinkInfo(url=extracted_page.url, base_url=page.base_url)
                    storage_links_q.put(link_info)
                    category.total_products += 1
                    log.debug(f'Adding product page {extracted_page}')
                    url_queue.put(extracted_page)
            category.completed_search_pages += 1
            category_status[page.base_url] = category
            log.debug(f'SP {category_status}')
            data_lock.release()
        elif page.page_type == PageType.PRODUCT_PAGE:
            extracted_info: ProductInfo = extract_product(document_tree)
            extracted_info.base_url = page.base_url
            storage_info_q.put(extracted_info)
            with data_lock:
                category: CategoryStatus = category_status[page.base_url]
                completed_products = category.completed_products
                category.completed_products = completed_products + 1
                category_status[page.base_url] = category
            log.debug(f'{category=}')
        log.debug(f'{product_count=}')
    log.debug('Exitting processor loop')


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
    return (
        category.total_products == category.completed_products and
        category.total_search_pages == category.completed_search_pages and
        category.saved_products == category.total_products and
        category.saved_product_links == category.total_products
    )


def start(categories, num_pages: int, num_procs: int, output_links: str, output_details, q_timeout, *args, **kwargs):
    log.debug(f'Runnig with args {categories=}, {num_pages=}, {num_procs=}')
    f_links = open(output_links, 'w')
    f_details = open(output_details, 'w')
    f_links.write('[')
    f_details.write('[')
    f_links.flush()
    f_details.flush()
    mgr = Manager()
    categories = load_categories(categories)
    url_queue = mgr.Queue()
    response_queue = mgr.Queue()
    stop_ev = mgr.Event()
    fetchers = []
    processors = []
    category_status = mgr.dict()
    data_lock = mgr.Lock()
    storage_info_q = mgr.Queue()
    storage_links_q = mgr.Queue()
    storage_info_lock = mgr.Lock()
    storage_links_lock = mgr.Lock()
    for url in categories:
        page = Page(base_url=url, url=url,
                    page_type=PageType.SEARCH_PAGE, page_number=1)
        status = CategoryStatus(base_url=url, total_search_pages=num_pages)
        category_status[url] = status
        url_queue.put(page)
    for _ in range(num_procs):
        f = Process(target=fetcher, args=(
            url_queue, response_queue, stop_ev, q_timeout))
        f.start()
        fetchers.append(f)
    for _ in range(num_procs):
        p = Process(target=processor, args=(response_queue, url_queue,
                    q_timeout, stop_ev, category_status, data_lock, storage_info_q, storage_links_q))
        p.start()
        processors.append(p)
    #links_storage_process = Process(target=None)
    details_storage_process = Process(target=save_product_info, args=(
        storage_info_q, f_details, storage_info_lock, stop_ev, q_timeout, category_status, data_lock))
    details_storage_process.start()
    links_storage_process = Process(target=save_product_link, args=(
        storage_links_q, f_links, storage_links_lock, stop_ev, q_timeout, category_status, data_lock))
    links_storage_process.start()
    while not stop_ev.is_set():
        sleep(5)
        data_lock.acquire()
        if all(category_is_completed(category) for category in category_status.values()):
            stop_ev.set()
        data_lock.release()
        log.debug(f'MP {category_status}')
    for p in chain(fetchers, processors):
        p.join()
    details_storage_process.join()
    links_storage_process.join()
    # FIXME: remove this extra object and traling comma
    storage_info_lock.acquire()
    f_links.write('{}]')
    f_details.flush()
    storage_info_lock.release()

    storage_links_lock.acquire()
    f_links.flush()
    f_details.write('{}]')
    storage_links_lock.release()

    f_details.close()
    f_links.close()
