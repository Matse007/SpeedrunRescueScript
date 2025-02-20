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
import asyncio
import pathlib

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

twitch_url_regex = re.compile(r"(https?:\/\/)?(?:www\.)?(?:m.)?(?:secure\.)?twitch\.tv\/\S*", re.IGNORECASE)
def is_twitch_url(url):
    # Checking with regex if its a twitch highlight
    return twitch_url_regex.search(url)

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
            if is_twitch_url(uri):
                twitch_urls.append(uri)

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

    await client.fetch_info(all_twitch_urls)
    client.write_twitch_users_at_risk()

    return highlights

def format_date_of_submission(dateobj):
    try:
        formatted_date = datetime.fromisoformat(dateobj).strftime("%B %d, %Y")
    except (KeyError, ValueError, TypeError):
        formatted_date = "Unknown date"
    return formatted_date

def save_highlights(highlights, client, highlights_filename, remaining_downloads_filename, highlights_json_filename):
    #saving all highlights in a formatted way for the user i guess? My hope is I can automate uploads later
    num_at_risk = 0
    
    for highlight in highlights:
        new_twitch_urls = []
        at_risk = False
        for twitch_url in highlight["urls"]:
            if client.is_video_at_risk(twitch_url):
                at_risk = True
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
            f.write(f"Run ID: {entry['run_id']}\n")
            f.write(f"Channel exceeds 100h limit: {entry['at_risk']}\n")
            f.write(f"Comment: {entry['comment']}\n")
            vod_sites = entry.get("vod_sites")
            if vod_sites is not None:
                f.write(f"Vod sites: {' '.join(vod_sites)}\n")

            f.write("-" * 50 + "\n")

    urls = [url for entry in highlights for url in entry["urls"]]
    with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=4)
    with open(highlights_json_filename, "w", encoding="utf-8") as f:
        json.dump(highlights, f, indent=4)

def download_videos(remaining_downloads_filename, video_folder_name, download_type_str, game_or_username):
    #pathlib.Path(download_folder_name).mkdir(parents=True, exist_ok=True)
    #downloading videos out of the provided dict using the yt-dlp module.
    ydl_options = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{video_folder_name}/videos/{download_type_str}/{game_or_username}/%(title)s.%(ext)s',
        'noplaylist': True,
        'match_filter': filter_live, #uses a function to determine if the dead link now links to a stream and accidentially starts to download this instead. Hopefully should skip livestreams
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

            first_url = urls[0]
            if first_url.endswith("*****"):
                first_url = first_url.replace("*****", "")
                print(f"Downloading: {str(first_url)}")
                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    try:
                        ydl.download([first_url])

                    except yt_dlp.utils.DownloadError as e:
                        print(f"Skipping invalid or dead link: {first_url} - Error: {e}")
                        urls.pop(0)
                        with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                            json.dump(urls, f, indent=4)
                        continue
    
                    except yt_dlp.utils.ExtractorError as e:
                        #In case you get rate limited. I did. It automatically goes through all downloads in this case and removes the urls unfairly.
                        if "HTTP Error 403: Forbidden" in str(e):
                            print(f"Error: {e}")
                            print("There is a rate limit or some other access restriction (403 Forbidden).")
                            if input("Do you want to stop and resume later? \nYour progress so far has been stored in the remaining_downloads.json (y/n): ").strip().lower().startswith("y"):
                                with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                                    json.dump(urls, f, indent=4)
                                print("Progress saved. You can resume the download later.")
                                return  # Exit the function and resume later
            else:
                print(f"Skipping url {first_url}! (Not in danger)")

            urls.pop(0)
            with open(remaining_downloads_filename, "w", encoding="utf-8") as f:
                json.dump(urls, f, indent=4)

        except FileNotFoundError:
            print("No remaining downloads file found")
            break
        except json.JSONDecodeError:
            print("Error reading JSON file")
            break
        except yt_dlp.utils.DownloadError as e:
            print(f"Failed to download {first_url}: {e}")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")

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
    pathlib.Path("output").mkdir(exist_ok=True)
    with open("config.json", "r") as f:
        config = json.load(f)

    game = config["game"]
    if game:
        download_type_str = "game"
        game_or_username = game
        is_game = True
    else:
        username = config["username"]
        if not username:
            raise RuntimeError("Neither username nor game specified!")

        download_type_str = "user"
        game_or_username = username
        is_game = False

    highlights_filename = f"output/twitch_highlights.{download_type_str}.{game_or_username}.txt"
    highlights_json_filename = f"output/twitch_highlights.{download_type_str}.{game_or_username}.json"
    remaining_downloads_filename = f"output/remaining_downloads.{download_type_str}.{game_or_username}.json"

    #Check if there are remaining Downloads left.
    remaininDownloads = load_remaining_downloads(remaining_downloads_filename)
    if remaininDownloads and input("A remaining downloads file has been found. Do you want to continue the download? (y/n): ").lower().startswith("y"):
        download_videos(remaining_downloads_file, config["video_folder_name"], download_type_str, game_or_username)
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

    client = await twitch_integration.TwitchClient.init(config)
    # Checking for highlights
    highlights = await process_runs(runs, client)
    print(f"Found {len(highlights)} Twitch highlights")

    # Save highlights
    save_highlights(highlights, client, highlights_filename, remaining_downloads_filename, highlights_json_filename)
    print(f"Saved highlights to {highlights_filename}")

    # Download prompt for users and downloading videos
    if highlights and config["download_videos"]:
        download_videos(remaining_downloads_filename, config["video_folder_name"], download_type_str, game_or_username)
        print("Download completed")

if __name__ == "__main__":
    asyncio.run(main())
