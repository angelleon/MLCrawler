from multiprocessing import Event, Queue
from random import choice

import requests

"""https://developers.whatismybrowser.com/useragents/explore/"""
user_agents = (
    ("Edge",     "98", "Win10", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36 Edg/98.0.1108.43"),
    ("Safari",     "15.4", "MacOS",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15"),
    ("Chrome",     "97", "Win10",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"),
    ("Safari",     "15.4", "iPhone",
     "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1"),
    ("Firefox",    "100", "Win10",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0"),
    ("Chrome",     "101", "Android",
     "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Mobile Safari/537.36"),
    ("Google bot", "2.1", "",
     "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
)


def fetcher(url: str, buffer: Queue, stop_env: Event):
    user_agent = choice(user_agents)
    headers = {
        "User-Agent": user_agent[1]
    }
    resp = requests.get(url, headers=headers)
    buffer.put(resp)


def processer(buffer: Queue, timeout: int = 2, stop_env: Event):
    while not stop_env.is_set():
        if resp := buffer.get(timeout=timeout) is None:
            break


def start(*args, **kwargs):
    stop_env = Event()
