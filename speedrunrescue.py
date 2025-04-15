#!/usr/bin/env python
import re
import time
import requests
from urllib.parse import quote
from isodate import parse_duration
import yt_dlp
import yt_dlp.postprocessor
import json
from datetime import datetime
import srcomapi
import twitch_integration
from twitch_integration import twitch_c_v_url_regex, twitch_current_url_regex
import asyncio
import pathlib
import configargparse
import traceback
import sys

# Configuration
BASE_URL = "https://www.speedrun.com/api/v1"
RATE_LIMIT = 0.6  # 600ms between requests because rate limits. Something I learned today
DEBUG_FILE = "debug_log.txt"
HIGHLIGHTS_FILE = "twitch_highlights_mmbn5.txt"
HIGHLIGHTS_JSON = "twitch_highlights_mmbn5.json"
DOWNLOADS_REMAINING_FILE = "downloads_remaining_mmbn5.json"
timestamp = time.time()
jsonData ={}

def get_user_id(username):
    #getting the userid first from their username
    try:
        data = srcomapi.get(f"/users/{quote(username)}")
        return data['data']['id']
    except KeyError:
        print("Invalid username or API error")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

def get_game_id(game):
    data = srcomapi.get(f"/games?abbreviation={game}&max=1&_bulk=yes")

    game_id = data["data"][0]["id"]
    return game_id

def get_personal_bests(user_id):
    run_ids = []
    url = f"/users/{user_id}/personal-bests?embed=game,category"
    try:
        # Fetch all personal bests in a single request
        data = srcomapi.get(url)
        # Extract the runs from the response
        if data and 'data' in data:
            for pb in data['data']:
                pb = pb['run']['id']
                run_ids.append(pb)
            return set(run_ids)
        else:
            print("No personal bests found or invalid response from the API.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching personal bests: {e}")
        return []

def get_all_runs(user_id):
    #gettign all runs with pagination in mind.
    runs = []
    offset = 0
    direction = "asc"
    last_id = ""

    while True:
        url = f"/runs?user={user_id}&max=200&offset={offset}&status=verified&embed=game,category,players&direction={direction}&orderby=date"
        try:
            data = srcomapi.get(url)
            if last_id:
                found_duplicate = False
                for index, run in enumerate(data['data']):
                    if run['id'] == last_id:
                        runs.extend(data['data'][0:index])
                        found_duplicate = True
                        break
                if found_duplicate:
                    break
            runs.extend(data['data'])
            # Pagination check
            if data['pagination']['size'] < 200:
                break
            offset += 200
            if offset >= 10_000:
                if not last_id:
                    last_id = runs[-1]["id"]
                    direction = "desc"
                    offset = 0
                else:
                    break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching runs: {e}")
            break
    return runs

def get_all_runs_from_game(game_id):
    runs = []
    offset = 0
    direction = "asc"
    last_id = ""

    while True:
        url = f"/runs?game={game_id}&max=200&offset={offset}&status=verified&embed=game,category,players&direction={direction}&orderby=date"
        try:
            print(f"offset: {offset}")
            data = srcomapi.get(url)
            if last_id:
                found_duplicate = False
                for index, run in enumerate(data['data']):
                    if run['id'] == last_id:
                        runs.extend(data['data'][0:index])
                        found_duplicate = True
                        break
                if found_duplicate:
                    break
            runs.extend(data['data'])

            # Pagination check
            if data['pagination']['size'] < 200:
                break
            offset += 200
            if offset >= 10_000:
                if not last_id:
                    last_id = runs[-1]["id"]
                    direction = "desc"
                    offset = 0
                else:
                    break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching runs: {e}")
            break

    return runs

twitch_url_regex = re.compile(r"(https?:\/\/)?(?:\w+\.)?twitch\.tv\/\S*", re.IGNORECASE)

IS_NOT_TWITCH_URL = 0
IS_TWITCH_URL_BUT_NOT_TWITCH_VIDEO_URL = 1
IS_TWITCH_VIDEO_URL = 2

def is_twitch_video_url(url):
    # Checking with regex if its a twitch highlight
    is_base_twitch_url = twitch_url_regex.search(url)
    if is_base_twitch_url:
        if twitch_current_url_regex.search(url) or twitch_c_v_url_regex.search(url):
            return IS_TWITCH_VIDEO_URL
        else:
            return IS_TWITCH_URL_BUT_NOT_TWITCH_VIDEO_URL
    else:
        return IS_NOT_TWITCH_URL

#Checking if a stream is live. Only happens if its an old dead link that redirects to the channel and the channel is live
def filter_live(info):
    # If the video is live, return a string indicating the reason for skipping.
    if info.get('is_live', False):
        return "Skipping live stream"
    # Otherwise, return None to allow the video.
    return None

async def process_runs(runs, client, ignore_links_in_description):
    #Extract Twitch highlight urls from runs
    highlights = []
    all_twitch_urls = []
    for run in runs:
        videos = run.get('videos') or {}
        links = videos.get('links') or []
        twitch_urls = []
        if ignore_links_in_description and links:
            links = [links[-1]]
        for video in links:
            uri = video.get('uri', '')
            result = is_twitch_video_url(uri)
            if result == IS_TWITCH_VIDEO_URL:
                twitch_urls.append(uri)
            elif result == IS_TWITCH_URL_BUT_NOT_TWITCH_VIDEO_URL:
                print(f"Skipped non-video twitch url {uri}")

        if len(twitch_urls) != 0:
            player_twitch_yt_urls = []
            player_datas = run["players"]["data"]
            player_names = []
            for player in player_datas:
                if player["rel"] == "guest":
                    player_names.append(player["name"])
                else:
                    twitch_info = player.get("twitch")
                    if twitch_info is not None:
                        player_twitch_yt_urls.append(twitch_info["uri"])

                    youtube_info = player.get("youtube")
                    if youtube_info is not None:
                        player_twitch_yt_urls.append(youtube_info["uri"])

                    player_names.append(player["names"]["international"])

            highlight = {
                'players': player_names,
                'game': run['game']['data']['names']['international'],
                'abbreviation': run['game']['data']['abbreviation'],
                'category': run['category']['data']['name'],
                'time': run['times']['primary'],
                'urls': twitch_urls,
                'run_id': run['id'],
                'submitted': run.get('submitted', 'Unknown date'),
                'date': run.get('date', 'Unknown date'),
                'comment': run.get('comment', '')
            }

            all_twitch_urls.extend(twitch_urls)
            if len(player_twitch_yt_urls) != 0:
                highlight["vod_sites"] = player_twitch_yt_urls

            highlights.append(highlight)

    if client.twitch is not None:
        await client.fetch_info(all_twitch_urls)
        client.write_twitch_users_at_risk()

    return highlights

def format_date_of_submission(dateobj):
    try:
        formatted_date = datetime.fromisoformat(dateobj).strftime("%B %d, %Y")
    except (KeyError, ValueError, TypeError):
        formatted_date = "Unknown date"
    return formatted_date

def save_highlights(highlights, client, is_game, highlights_filename, remaining_downloads_filename, highlights_json_filename):
    #saving all highlights in a formatted way for the user i guess? My hope is I can automate uploads later
    num_at_risk = 0

    for highlight in highlights:
        new_twitch_urls = []
        at_risk = False
        for twitch_url in highlight["urls"]:
            if not is_game:
                at_risk = True
            else:
                at_risk = client.is_video_at_risk(twitch_url)

            if at_risk:
                new_twitch_urls.append(f"{twitch_url}*****")
            else:
                new_twitch_urls.append(twitch_url)

        highlight["urls"] = new_twitch_urls
        highlight["at_risk"] = at_risk
        if at_risk:
            num_at_risk += 1

    print(f"Number of at-risk runs: {num_at_risk}")

    with open(highlights_filename, "w", encoding="utf-8") as f:
        for entry in highlights:
            #formatting the iso format

            f.write(f"Players: {', '.join(entry['players'])}\n")
            f.write(f"Category: {entry['category']}\n")
            f.write(f"Time: {str(parse_duration(entry['time']))}\n")
            f.write(f"Submitted Date: {format_date_of_submission(entry['submitted'])}\n")
            f.write(f"Run Date: {format_date_of_submission(entry['date'])}\n")
            f.write(f"URL: {' '.join(entry['urls'])}\n")
            f.write(f"SRC Link: https://speedrun.com/{entry['abbreviation']}/runs/{entry['run_id']}\n")
            f.write(f"Channel exceeds 100h limit: {entry['at_risk']}\n")
            f.write(f"Comment: {entry['comment']}\n")
            vod_sites = entry.get("vod_sites")
            if vod_sites is not None:
                f.write(f"Vod sites: {' '.join(vod_sites)}\n")

            f.write("-" * 50 + "\n")

    urls = []
    for entry in highlights:
        src_link = f"https://speedrun.com/{entry['abbreviation']}/runs/{entry['run_id']}"
        urls.extend((url, src_link) for url in entry["urls"])

    with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=4)
    with open(highlights_json_filename, "w", encoding="utf-8") as f:
        json.dump(highlights, f, indent=4)


def print_exception(e, additional_msg=""):
    error_msg = e.args[0] if len(e.args) >= 1 else "(Not provided)"

    output = f"""\



================================================================
======================== ERROR OCCURRED ========================
{additional_msg}{error_msg}
================================================================

-- DEBUG INFORMATION --
Error type: {e.__class__.__name__}
Traceback (most recent call last)
{''.join(traceback.format_tb(e.__traceback__))}"""

    print(output)

class DesiredQuality:
    __slots__ = ("download_best", "desired_height", "fallback_should_increase_quality")

    def __init__(self, download_best, desired_height, fallback_should_increase_quality):
        self.download_best = download_best
        self.desired_height = desired_height
        self.fallback_should_increase_quality = fallback_should_increase_quality

    @classmethod
    def from_string(cls, input_str):
        input_str = input_str.strip()
        if input_str == "best":
            return cls(True, 0, False)

        if input_str.startswith("<="):
            fallback_should_increase_quality = False
            input_str = input_str[2:]
        elif input_str.startswith(">="):
            fallback_should_increase_quality = True
            input_str = input_str[2:]
        else:
            fallback_should_increase_quality = True

        if input_str[-1] == "p":
            input_str = input_str[:-1]

        try:
            desired_height = int(input_str)
        except ValueError:
            raise RuntimeError(f"Invalid format for `video-quality` (got: {input_str}). Please specify the video quality or desired height of the video, e.g. 360p, 720, 1080, 542. You can also add >= or <= before the quality to tell the program whether to download the closest higher quality or closest lower quality, respectively, if the quality does not exist. If you omit >= and <=, it defaults to choosing the closest higher quality.")

        return cls(False, desired_height, fallback_should_increase_quality)

class QualityPostprocessor(yt_dlp.postprocessor.PostProcessor):
    __slots__ = ("desired_height", "fallback_should_increase_quality")

    def __init__(self, desired_quality):
        super(QualityPostprocessor, self).__init__(None)
        self.desired_height = desired_quality.desired_height
        self.fallback_should_increase_quality = desired_quality.fallback_should_increase_quality

    @staticmethod
    def is_format_source(quality_format):
        # No hard and fast rule, so test multiple things
        if "source" in quality_format["format_id"].lower() or "source" in quality_format.get("format_note", "").lower() or "source" in quality_format.get("format", "").lower():
            return True
        else:
            return False

    def run(self, info):
        best_height = 0
        best_tbr = 0
        best_format_id = None
        source_format = None
        source_format_id = None

        formats_sorted_by_height = sorted(info["formats"], key=lambda x: x.get("height", 0))

        #with open("video_info.json", "w+") as f:
        #    json.dump(info, f, indent=2)
        #
        #with open("formats_sorted_by_height.json", "w+") as f:
        #    json.dump(formats_sorted_by_height, f, indent=2)

        #print(f"formats_sorted_by_height: {formats_sorted_by_height}")
        for quality_format in formats_sorted_by_height:
            if quality_format["vcodec"] == "none":
                #print(f"Continued {quality_format}")
                continue

            format_id = quality_format["format_id"]
            # some videos e.g. https://www.twitch.tv/videos/118628100
            # have no height associated with some formats
            # not really sure how to integrate this into the current quality filtering logic, so just skip these for now
            height = quality_format.get("height")
            if height is None:
                continue

            tbr = quality_format["tbr"]
            is_source = QualityPostprocessor.is_format_source(quality_format)

            if is_source:
                source_format = quality_format

            #print(f"best_height: {best_height}, height: {height}, self.desired_height: {self.desired_height}, is_source: {is_source}, quality_format: {quality_format}\n\n\n")

            if best_height == 0 or height < self.desired_height:
                best_height = height
                best_tbr = tbr
                best_format_id = format_id
            # edge case for when there are multiple formats with the same height and we have to choose between them
            elif height == self.desired_height:
                # if the best height isn't even the desired height yet, then set it so
                # otherwise, it is, and we need to choose out of the two which to pick
                # I think this only happens when one is source quality

                if best_height != self.desired_height or is_source:
                    best_height = height
                    best_tbr = tbr
                    best_format_id = format_id
            # only do this logic if we want to fallback to a higher quality
            # if the height we chose doesn't match the desired height
            elif self.fallback_should_increase_quality:
                # if the current best height is less than the desired height, and we want to fallback to quality higher
                # edge case to pick the source quality when we meet qualities with the same height
                if best_height < self.desired_height or (best_height == height and is_source):
                    best_height = height
                    best_tbr = tbr
                    best_format_id = format_id

        # Sometimes, the source format size can be less than encoded formats at a lower resolution
        # if this is true for the best format we picked, then choose the source format
        if source_format is not None and source_format.get("tbr") is not None and best_tbr is not None and source_format["tbr"] < best_tbr:
            best_format_id = source_format["format_id"]

        # include audio format just in case somehow, the best video format has no audio
        new_formats = [quality_format for quality_format in info["formats"] if quality_format["format_id"] == best_format_id or (quality_format["acodec"] != "none" and quality_format["vcodec"] == "none")]

        # if we somehow can't find any formats, then just try to download anything
        if len(new_formats) != 0:
            info["formats"] = new_formats

        #print(f"Post processor info: {info}")

        return [], info

def download_videos(remaining_downloads_filename, video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, allow_all, desired_quality, concurrent_fragments):
    #pathlib.Path(download_folder_name).mkdir(parents=True, exist_ok=True)
    #downloading videos out of the provided dict using the yt-dlp module.

    download_info_template = """\
URL: %(original_url)s
speedrun.com URL: {src_url}
Channel: %(uploader_id)s
Title: %(title)s
Date: %(upload_date>%Y-%m-%d)s
Duration: %(duration>%H:%M:%S)s
Description:
%(description)s
=========================================================="""

    print_to_file_list = [[download_info_template, downloaded_video_info_filename]]

    ydl_options = {
        'format': "bestvideo+bestaudio/best",
        'outtmpl': f'{video_folder_name}/{download_type_str}/{game_or_username}/%(title)s_%(id)s_%(format_id)s.%(ext)s',
        'noplaylist': True,
        'match_filter': filter_live, #uses a function to determine if the dead link now links to a stream and accidentially starts to download this instead. Hopefully should skip livestreams
        "print_to_file": {"after_video": print_to_file_list},
        'verbose': True, # for debugging stuff
        'sleep-interval': 5, #so i dont get insta blacklisted by twitch
        'retries': 1,  # Retry a second time a bit later in case there was simply an issue
        'retry-delay': 10,  # Wait 10 seconds before retrying
        'concurrent_fragment_downloads': concurrent_fragments,
    }

    if desired_quality.download_best:
        quality_postprocessor = None
    else:
        quality_postprocessor = QualityPostprocessor(desired_quality)

    while True:
        try:
            # Load URLs from JSON file
            with open(remaining_downloads_filename, "r", encoding="utf-8") as f:
                urls = json.load(f)

            # Stop if no URLs are left
            if not urls:
                print("All downloads completed!")
                break

            url_info = urls[0]
            if isinstance(url_info, list):
                current_url, src_link = url_info
            else:
                current_url = url_info
                src_link = "N/A"

            sleep_time = 15
            if allow_all or current_url.endswith("*****"):
                clean_url = current_url.replace("*****", "") # Cleaning up the extraspacing
                print(f"Downloading: {clean_url}")
                print_to_file_list[0][0] = download_info_template.format(src_url=src_link)
                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    if quality_postprocessor is not None:
                        ydl.add_post_processor(quality_postprocessor, when="pre_process")

                    try:
                        ydl.download([clean_url])
                    except Exception as e:
                        error_msg = e.args[0] if len(e.args) >= 1 else ""
                        # Video does not exist
                        # video_does_not_exist_regex = re.compile(r"Video \w+ does not exist", flags=re.IGNORECASE) <-- seemed not to work. as a quick fix i disabled it and check manually
                        if ("does not exist" in error_msg) or ("The channel is not currently live" in error_msg):
                            print(f"Skipping invalid or dead link: {clean_url}")
                            with open(downloaded_video_info_filename, "a+") as f:
                                f.write(f"{clean_url} for {src_link} does not exist\n==========================================================\n")
                            #sleep_time = 15

                        else:
                            print_exception(e, f"Failed to download {clean_url}: ")
                            with open(downloaded_video_info_filename, "a+") as f:
                                f.write(f"Failed to download {clean_url}: {error_msg}\n==========================================================\n")
            else:
                print(f"Skipping {current_url} (not marked as at-risk)")
                sleep_time = 0

            urls.pop(0)
            with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                json.dump(urls, f, indent=4)
            if sleep_time != 0:
                print(f"Waiting {sleep_time} seconds before downloading the next video.")
                time.sleep(sleep_time)
        except FileNotFoundError:
            print("No remaining downloads file found")
            break
        except json.JSONDecodeError:
            print("Error reading JSON file")
            break
        except KeyboardInterrupt:
            print("\nDownload interrupted by user. Progress saved.")
            with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                json.dump(urls, f, indent=4)
            break
        except Exception as e:
            print_exception(e, "Unexpected error: ")
            print(f"Unexpected error: {e}")
            break

def load_remaining_downloads(remaining_downloads_filename):
    try:
        with open(remaining_downloads_filename, "r", encoding="utf-8") as f:
            urls = json.load(f)
        if not urls:
            print("No remaining downloads file found")
            return None
        return urls
    except FileNotFoundError:
        print("No remaining downloads file found")
    except json.JSONDecodeError:
        print("Error reading JSON file")
    except Exception as e:
        print(f"Unexpected error: {e}")

def convert_bool(value):
    value_str_lower = value.lower()
    if value_str_lower == "true":
        return True
    elif value_str_lower == "false":
        return False
    else:
        raise configargparse.ArgumentTypeError(f"Invalid bool type (must be `true` or `false`, got {value})")

def process_personal_bests(runs, pb_ids):
    return [run for run in runs if run["id"] in pb_ids]

async def main():
    ap = configargparse.ArgumentParser(
        allow_abbrev=False,
        config_file_parser_class=configargparse.YAMLConfigFileParser,
        config_file_open_func=lambda filename: open(
            filename, "r", encoding="utf-8"
        )
    )

    ap.add_argument("-cfg", "--config", dest="config", default="config.yml", is_config_file=True, help="Alternative config file to put in command line arguments. Arguments provided on the command line will override arguments provided in the config file, if specified.")
    ap.add_argument("--game", dest="game", default=None, help="The game of the leaderboard you want to scrape for Twitch links. Either this or `username:` must be specified")
    ap.add_argument("--username", dest="username", default=None, help="The speedrun.com username for the runs you want to scrape for Twitch links. Either this or `game:` must be specified")
    ap.add_argument("--app-id", dest="app_id", default=None, help="Name of the Twitch API App ID used for checking if a user has 100 or more hours of highlights. Required for game download. Not necessary for username download.")
    ap.add_argument("--app-secret", dest="app_secret", default=None, help="Name of the Twitch API App Secret. See `app-id:` for more info")
    ap.add_argument("--video-folder-name", dest="video_folder_name", default="videos", help="Folder where the videos will be stored. Videos will automatically be sorted by game and username. Will be created if it doesn't exist already. Default is a folder \"videos\" in the same directory as the script")
    ap.add_argument("--cache-filename", dest="cache_filename", default="twitch_cache.json", help="File containing information about users' videos from the Twitch API (for determining if a user has >= 100 hours of highlights). Default is twitch_cache.json")
    ap.add_argument("--download-videos", dest="download_videos", type=convert_bool, help="Whether to download videos after scraping them from speedrun.com", required=True)
    ap.add_argument("--allow-all", dest="allow_all", type=convert_bool, help="Whether to download all found videos regardless of whether or not the channel they exist on have reached the >=100h highlight limit.", required=True)
    ap.add_argument("--video-quality", dest="video_quality", default="best", help="Desired closest video quality that you want to download. For this option, specify the video quality or desired height of the video, e.g. 360p, 720, 1080, 542. Choosing \"best\" will just download the best quality available. THIS OPTION SHOULD BE IN QUOTES, i.e. do \"360p\", not 360p. You can also add >= or <= before the quality to tell the program whether to download the closest higher quality or closest lower quality, respectively, if the quality does not exist. If you omit >= and <=, it defaults to choosing the closest higher quality. Defaults to \"best\".")
    ap.add_argument("--ignore-links-in-description", dest="ignore_links_in_description", type=convert_bool, help="Whether to ignore twitch links that are in the video description or not. By default this is disabled.", required=True)
    ap.add_argument("--concurrent-fragments", dest="concurrent_fragments", type=int, help="How many concurrent fragments to download of a video. By default this is 1.")
    ap.add_argument("--safe-only-pbs", dest="save_only_pbs", type=convert_bool,help="If set to true, only the PBs of the runner or all PBs on the leaderboard are being saved.",required=True)
    args = ap.parse_args()

    desired_quality = DesiredQuality.from_string(args.video_quality)

    print(f"Using quality: {args.video_quality}")

    if args.game and args.username:
        raise RuntimeError("Only one of `username:` or `game:` must be specified in config.yml!")

    game = args.game
    username = args.username
    if game:
        download_type_str = "game"
        game_or_username = game
        is_game = True
    elif not username:
        raise RuntimeError("One of `username:` or `game:` must be specified in config.yml!")
    else:
        download_type_str = "user"
        game_or_username = username
        is_game = False

    base_output_dirpath = pathlib.Path(f"output/{download_type_str}/{game_or_username}")
    base_output_dirpath.mkdir(parents=True, exist_ok=True)

    highlights_filename = f"{base_output_dirpath}/twitch_highlights.txt"
    highlights_json_filename = f"{base_output_dirpath}/twitch_highlights.json"
    remaining_downloads_filename = f"{base_output_dirpath}/remaining_downloads.json"
    downloaded_video_info_filename = f"{base_output_dirpath}/download_info.txt"

    concurrent_fragments = args.concurrent_fragments or 1

    #Check if there are remaining Downloads left.
    remaininDownloads = load_remaining_downloads(remaining_downloads_filename)
    if remaininDownloads and input("A remaining downloads file has been found. Do you want to continue the download? (y/n): ").lower().startswith("y"):
        download_videos(remaining_downloads_filename, args.video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, args.allow_all, desired_quality, concurrent_fragments)
        return

    if is_game:
        print(f"Searching for {game}...")
        game_id = get_game_id(game)
        print(f"Getting all runs")
        runs = get_all_runs_from_game(game_id)
    else:
        print(f"Searching for {username}...")
        # Getting the user id first from the username.
        user_id = get_user_id(username)
        if not user_id:
            print("User not found")
            return

        # Fetch all runs from user
        print("Fetching runs...")
        runs = get_all_runs(user_id)
        if args.save_only_pbs:
            pb_ids = get_personal_bests(user_id)
            runs = process_personal_bests(runs, pb_ids)

    print(f"Found {len(runs)} verified runs")

    if (args.app_id is None or args.app_secret is None) and is_game:
        raise RuntimeError("Twitch integration must be present if you are requesting a game to be downloaded")
    client = await twitch_integration.TwitchClient.init(args)
    # Checking for highlights
    highlights = await process_runs(runs, client, args.ignore_links_in_description)
    print(f"Found {len(highlights)} Twitch highlights")

    # Save highlights
    save_highlights(highlights, client, is_game, highlights_filename, remaining_downloads_filename, highlights_json_filename)
    print(f"Saved highlights to {highlights_filename}")

    # Download prompt for users and downloading videos
    if highlights and args.download_videos:
        download_videos(remaining_downloads_filename, args.video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, args.allow_all, desired_quality, concurrent_fragments)
        print("Download completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print_exception(e)
        sys.exit(1)
