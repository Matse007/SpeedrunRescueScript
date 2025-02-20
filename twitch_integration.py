from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
import asyncio
import json
import pathlib
import itertools
import re

twitch_c_v_url_regex = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:m.)?(?:secure\.)?twitch\.tv\/(\w+)\/([cv])\/(\d+)", re.IGNORECASE)
twitch_current_url_regex = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:m.)?(?:secure\.)?twitch\.tv\/videos/(\d+)", re.IGNORECASE)

def grouper(iterable, n):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, n))
        if not chunk:  # Stop when no more elements are left
            break
        yield chunk

duration_regex = re.compile(r"^(?:([0-9]+)h)?(?:([0-9]+)m)?(?:([0-9]+)s?)?$")

def parse_duration(duration):
    match_obj = duration_regex.match(duration.strip())
    if match_obj:
        hours = match_obj.group(1)
        minutes = match_obj.group(2)
        seconds = match_obj.group(3)
        if hours is None and minutes is None and seconds is None:
            raise RuntimeError(f"Invalid duration \"{expiry_time}\" provided for expiry time!")

        if hours is None:
            hours = 0
        if minutes is None:
            minutes = 0
        if seconds is None:
            seconds = 0

        try:
            duration_as_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        except ValueError:
            raise RuntimeError(f"At least one of hours, seconds, and minutes not an integer!")
    else:
        raise RuntimeError(f"Invalid duration \"{expiry_time}\" provided for expiry time!")

    return duration_as_seconds

class UserCache:
    __slots__ = ("cache_filename", "cache_info")

    def __init__(self, cache_filename):
        cache_filepath = pathlib.Path(cache_filename)
        if cache_filepath.is_file():
            with open(cache_filename, "r") as f:
                cache_info = json.load(f)
        else:
            cache_info = {
                "video_infos": {},
                "user_infos": {},
                "total_duration": -1
            }

        self.cache_info = cache_info
        self.cache_filename = cache_filename

    def parse_valid_video_id(self, video_url, update_c=False):
        match_obj = twitch_c_v_url_regex.match(video_url)
        if match_obj:
            url_type = match_obj.group(2)
            if url_type == "c":
                if update_c:
                    user_info = self.get_user_info(match_obj.group(1))
                    user_info["c_video_urls"].append(video_url)
                    print(f"Skipped c-type url {video_url}")
                video_id = None
            else:
                video_id = match_obj.group(3)
        else:
            match_obj = twitch_current_url_regex.match(video_url)
            if match_obj:
                video_id = match_obj.group(1)
            else:
                print(f"Skipped non-video url {video_url}")
                video_id = None

        return video_id

    async def update_video_infos_from_video_urls(self, twitch, video_urls):
        valid_nonfound_video_ids = []
        print("Finding valid video ids!")
        for video_url in video_urls:
            video_id = self.parse_valid_video_id(video_url, update_c=True)
            if video_id is not None:
                video_info = self.cache_info["video_infos"].get(video_id)
                if video_info is None:
                    valid_nonfound_video_ids.append(video_id)

        if len(valid_nonfound_video_ids) != 0:
            print(f"Fetching video info from {len(valid_nonfound_video_ids)} valid video ids!")
            for i, valid_nonfound_video_ids_chunk in enumerate(grouper(valid_nonfound_video_ids, 100)):
                print(f"video_ids_chunk: {valid_nonfound_video_ids_chunk}")
                print(f"Parsing chunk {100*i}")
                async for video_info_obj in twitch.get_videos(ids=valid_nonfound_video_ids_chunk, first=100):
                    video_info = video_info_obj.to_dict()
                    self.cache_info["video_infos"][video_info["id"]] = video_info
            
            valid_nonfound_video_ids_as_set = frozenset(valid_nonfound_video_ids)
            found_video_info_ids = frozenset(self.cache_info["video_infos"].keys())
            missing_video_ids = valid_nonfound_video_ids_as_set - found_video_info_ids

            for missing_video_id in missing_video_ids:
                self.cache_info["video_infos"][missing_video_id] = {"missing": True}

        self.save_cache()

    async def update_user_infos_from_video_infos(self, twitch):
        for video_id, video_info in self.cache_info["video_infos"].items():
            if video_info.get("missing"):
                continue

            username = video_info["user_login"]
            user_info = self.get_user_info(username)
            if len(user_info["videos"]) == 0:
                print(f"Downloading video info for {username}!")
                user_id = video_info["user_id"]
                num_video_infos = 0
                async for user_video_info_obj in twitch.get_videos(user_id=user_id, first=100):
                    user_video_info = user_video_info_obj.to_dict()
                    user_info["videos"][user_video_info["id"]] = user_video_info
                    num_video_infos += 1
                
                print(f"num_video_infos: {num_video_infos}")
                self.save_cache()

    def determine_at_risk_users(self):
        print(f"Determining at risk users!")
        for username, user_info in self.cache_info["user_infos"].items():
            total_duration = 0
            for video_id, user_video_info in user_info["videos"].items():
                total_duration += parse_duration(user_video_info["duration"])

            user_info["total_duration"] = total_duration

        self.save_cache()

    def is_video_at_risk(self, video_url):
        video_id = self.parse_valid_video_id(video_url)
        if video_id is None:
            return False
    
        video_info = self.cache_info["video_infos"].get(video_id)
        if video_info is None or video_info.get("missing"):
            return False

        username = video_info["user_login"]
        user_info = self.cache_info["user_infos"].get(username)
        if user_info is None:
            return False

        if user_info["total_duration"] >= 360000:
            return True
        else:
            return False

    def write_twitch_users_at_risk(self):
        twitch_users_sorted_by_total_duration = sorted(self.cache_info["user_infos"].items(), key=lambda x: x[1]["total_duration"], reverse=True)
        output = "".join(f"{username}: {user_info['total_duration']}\n" for username, user_info in twitch_users_sorted_by_total_duration)

        with open("output/twitch_users_sorted_by_total_duration.txt", "w+") as f:
            f.write(output)

    def get_user_info(self, username):
        user_info = self.cache_info["user_infos"].get(username)
        if user_info is None:
            user_info = {
                "c_video_urls": [],
                "videos": {}
            }
            self.cache_info["user_infos"][username] = user_info
        return user_info

    def save_cache(self):
        with open(self.cache_filename, "w+") as f:
            json.dump(self.cache_info, f, indent=2)

class TwitchClient:
    __slots__ = ("config", "twitch", "user_cache")

    def __init__(self, config, twitch):
        self.config = config
        self.twitch = twitch
        self.user_cache = UserCache(self.config["cache_filename"])

    @classmethod
    async def init(cls, config):
        app_id = config["app_id"]
        app_secret = config["app_secret"]
        twitch = await Twitch(app_id, app_secret)

        return cls(config, twitch)

    async def fetch_info(self, video_urls):
        await self.user_cache.update_video_infos_from_video_urls(self.twitch, video_urls)
        await self.user_cache.update_user_infos_from_video_infos(self.twitch)
        self.user_cache.determine_at_risk_users()

    def is_video_at_risk(self, video_url):
        return self.user_cache.is_video_at_risk(video_url)    

    def write_twitch_users_at_risk(self):
        self.user_cache.write_twitch_users_at_risk()
