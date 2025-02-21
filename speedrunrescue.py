import re
import time
import requests
from urllib.parse import quote
from isodate import parse_duration
import yt_dlp
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

def get_all_runs(user_id):
    #gettign all runs with pagination in mind.
    runs = []
    offset = 0

    while True:
        url = f"/runs?user={user_id}&max=200&offset={offset}&status=verified&embed=game,category,players"
        try:
            data = srcomapi.get(url)
            runs.extend(data['data'])
            # Pagination check
            if data['pagination']['size'] < 200:
                break
            offset += 200
        except requests.exceptions.RequestException as e:
            print(f"Error fetching runs: {e}")
            break
    return runs

def get_all_runs_from_game(game_id):
    runs = []
    offset = 0

    while True:
        url = f"/runs?game={game_id}&max=200&offset={offset}&status=verified&embed=game,category,players"
        try:
            print(f"offset: {offset}")
            data = srcomapi.get(url)
            runs.extend(data['data'])

            # Pagination check
            if data['pagination']['size'] < 200:
                break
            offset += 200
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

async def process_runs(runs, client):
    #Extract Twitch highlight urls from runs
    highlights = []
    all_twitch_urls = []
    for run in runs:
        videos = run.get('videos') or {}
        links = videos.get('links') or []
        twitch_urls = []
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
                    user_data = player.get("data", {})
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
    with open("config.json") as f:
        config = json.load(f)
    download_all = config.get("allow_all_downloads", False)
    
    for highlight in highlights:
        new_twitch_urls = []
        at_risk = False
        for twitch_url in highlight["urls"]:
            if download_all or not is_game:
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

video_does_not_exist_regex = re.compile(r"Video \w+ does not exist", flags=re.IGNORECASE)

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

def download_videos(remaining_downloads_filename, video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, allow_all):
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
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{video_folder_name}/{download_type_str}/{game_or_username}/%(title)s_%(id)s.%(ext)s',
        'noplaylist': True,
        'match_filter': filter_live, #uses a function to determine if the dead link now links to a stream and accidentially starts to download this instead. Hopefully should skip livestreams
        "print_to_file": {"after_video": print_to_file_list},
        'verbose': True, # for debugging stuff
        'sleep-interval': 5, #so i dont get insta blacklisted by twitch
        'retries': 1,  # Retry a second time a bit later in case there was simply an issue
        'retry-delay': 10,  # Wait 10 seconds before retrying
    }

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

            if allow_all or current_url.endswith("*****"):
                clean_url = current_url.replace("*****", "") # Cleaning up the extraspacing
                print(f"Downloading: {clean_url}")
                print_to_file_list[0][0] = download_info_template.format(src_url=src_link)
                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    try:
                        ydl.download([clean_url])
                    except Exception as e:
                        error_msg = e.args[0] if len(e.args) >= 1 else ""
                        # Video does not exist
                        if video_does_not_exist_regex.search(error_msg):
                            print(f"Skipping invalid or dead link: {clean_url}")
                            with open(downloaded_video_info_filename, "a+") as f:
                                f.write(f"{clean_url} for {src_link} does not exist\n==========================================================\n")

                        elif "HTTP Error 403: Forbidden" in error_msg:
                            print(f"You have been rate-limited, or something is preventing Twitch access. Your progress has been saved. Please try again later.")
                            sys.exit(1)
                        else:
                            print_exception(e, f"Failed to download {clean_url}: ")
                            sys.exit(1)
            else:
                print(f"Skipping {clean_url} (not marked as at-risk)")

            urls.pop(0)
            with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                json.dump(urls, f, indent=4)
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
    ap.add_argument("--download-videos", dest="download_videos", default=False, help="Whether to download videos after scraping them from speedrun.com", required=True)
    ap.add_argument("--allow-all", dest="allow_all", default=False, help="Whether to download all found videos regardless of whether or not the channel they exist on have reached the >=100h highlight limit.", required=True)

    args = ap.parse_args()

    if args.game and args.username:
        raise RuntimeError("Only one of `username:` or `game:` must be specified in config.yml!")

    game = args.game
    if game:
        download_type_str = "game"
        game_or_username = game
        is_game = True
    else:
        username = args.username
        if not username:
            raise RuntimeError("One of `username:` or `game:` must be specified in config.yml!")

        download_type_str = "user"
        game_or_username = username
        is_game = False

    base_output_dirpath = pathlib.Path(f"output/{download_type_str}/{game_or_username}")
    base_output_dirpath.mkdir(parents=True, exist_ok=True)

    highlights_filename = f"{base_output_dirpath}/twitch_highlights.txt"
    highlights_json_filename = f"{base_output_dirpath}/twitch_highlights.json"
    remaining_downloads_filename = f"{base_output_dirpath}/remaining_downloads.json"
    downloaded_video_info_filename = f"{base_output_dirpath}/download_info.txt"

    #Check if there are remaining Downloads left.
    remaininDownloads = load_remaining_downloads(remaining_downloads_filename)
    if remaininDownloads and input("A remaining downloads file has been found. Do you want to continue the download? (y/n): ").lower().startswith("y"):
        download_videos(remaining_downloads_filename, args.video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, args.allow_all)
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

    print(f"Found {len(runs)} verified runs")

    if (args.app_id is None or args.app_secret is None) and is_game:
        raise RuntimeError("Twitch integration must be present if you are requesting a game to be downloaded")
    client = await twitch_integration.TwitchClient.init(args)
    # Checking for highlights
    highlights = await process_runs(runs, client)
    print(f"Found {len(highlights)} Twitch highlights")

    # Save highlights
    save_highlights(highlights, client, is_game, highlights_filename, remaining_downloads_filename, highlights_json_filename)
    print(f"Saved highlights to {highlights_filename}")

    # Download prompt for users and downloading videos
    if highlights and args.download_videos:
        download_videos(remaining_downloads_filename, args.video_folder_name, downloaded_video_info_filename, download_type_str, game_or_username, args.allow_all)
        print("Download completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print_exception(e)    
        sys.exit(1)
