import traceback
import requests
import urllib
import pathlib
import json
import time
import re
import sys

class CacheSettings:
    __slots__ = ("read_cache", "write_cache", "cache_dirname", "rate_limit", "retry_on_empty")

    def __init__(self, read_cache, write_cache, cache_dirname, rate_limit):
        self.read_cache = read_cache
        self.write_cache = write_cache
        self.cache_dirname = cache_dirname
        self.rate_limit = rate_limit

default_cache_settings = CacheSettings(True, True, "srcom_cached", True)

def get_cached_endpoint_filepath(endpoint, params, cache_settings):
    endpoint_as_pathname = f"{cache_settings.cache_dirname}/{urllib.parse.quote(endpoint, safe='')}_q_{urllib.parse.urlencode(params, doseq=True)}.json"

    return pathlib.Path(endpoint_as_pathname)

API_URL = "https://www.speedrun.com/api/v1"

def get(endpoint, params=None, cache_settings=None, require_success=False):
    exception_sleep_time = 15

    while True:
        try:
            return get_in_loop_code(endpoint, params, cache_settings)[0]
        except ConnectionError as e:
            print(f"Exception occurred: {e}\n{''.join(traceback.format_tb(e.__traceback__))}\nSleeping for {exception_sleep_time} seconds now.")
            time.sleep(exception_sleep_time)
            exception_sleep_time *= 2
            if exception_sleep_time > 1000:
                exception_sleep_time = 1000

def get_in_loop_code(endpoint, params, cache_settings):
    if params is None:
        params = {}

    if cache_settings is None:
        cache_settings = default_cache_settings

    endpoint_as_path = get_cached_endpoint_filepath(endpoint, params, cache_settings)
    if cache_settings.read_cache and endpoint_as_path.is_file():
        error_code = None

        endpoint_as_path_size = endpoint_as_path.stat().st_size
        if endpoint_as_path_size == 0:
            return {}, 404

        #print(f"endpoint_as_path: {endpoint_as_path}")
        with open(endpoint_as_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if error_code is None:
            return data, 200

    url = f"{API_URL}{endpoint}"
    print(f"url: {url}?{urllib.parse.urlencode(params, doseq=True)}")
    start_time = time.time()
    r = requests.get(url, params=params)
    end_time = time.time()
    print(f"Request took {end_time - start_time}.")

    if cache_settings.write_cache:
        endpoint_as_path.parent.mkdir(parents=True, exist_ok=True)

    if r.status_code != 200:
        if r.status_code >= 400 and r.status_code < 500:
            raise RuntimeError(f"API returned {r.status_code}: {r.reason}")

        raise ConnectionError(f"Got status code {r.status_code}!")
        #return r.reason, r.status_code
        #if r.status_code != 404:
        #    raise ConnectionError(f"Got status code {r.status_code}!")
        #
        #if cache_settings.write_cache:
        #    if r.status_code == 404:
        #        endpoint_as_path.touch()
        #    else:
        #        print(f"Got non-404 error code: {r.status_code}")
        #        with open(endpoint_as_path, "w+") as f:
        #            f.write(str(r.status_code))
        #
        #return r.reason, r.status_code

    data = r.json()

    if cache_settings.write_cache:
        endpoint_as_path.parent.mkdir(parents=True, exist_ok=True)
        data_as_str = json.dumps(data, separators=(",", ":"))
        exit_after_write = False
        while True:
            try:
                with open(endpoint_as_path, "w+", encoding="utf-8") as f:
                    f.write(data_as_str)
                break
            except KeyboardInterrupt:
                print("Saving speedrun.com API cache, please stop Ctrl-C'ing")
                exit_after_write = True

        if exit_after_write:
            sys.exit(1)

    if cache_settings.rate_limit:
        time.sleep(1)

    return data, r.status_code
