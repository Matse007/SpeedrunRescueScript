import re
import time
import requests
from urllib.parse import quote
from isodate import parse_duration
import yt_dlp
import json

# Configuration
BASE_URL = "https://www.speedrun.com/api/v1"
RATE_LIMIT = 0.6  # 600ms between requests because rate limits. Something I learned today
DEBUG_FILE = "debug_log.txt"
HIGHLIGHTS_FILE = "twitch_highlights.txt"
DOWNLOADS_REMAINING_FILE = "downloads_remaining.json"
timestamp = time.time()
jsonData ={}

def req(url):
    global timestamp
    exec_time = time.time() - timestamp
    if exec_time < RATE_LIMIT:
        time.sleep(RATE_LIMIT - exec_time)

    response = requests.get(url)
    data = response.json()

    timestamp = time.time()
    return data

def get_user_id(username):
    #getting the userid first from their username
    try:
        data = req(f"{BASE_URL}/users/{quote(username)}")
        return data['data']['id']
    except KeyError:
        print("Invalid username or API error")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

def get_game_id(game):
    data = req(f"{BASE_URL}/games?abbreviation={game}&max=1&_bulk=yes")

    game_id = data["data"][0]["id"]
    return game_id

def get_all_runs(user_id):
    #gettign all runs with pagination in mind.
    runs = []
    offset = 0

    while True:
        url = f"{BASE_URL}/runs?user={user_id}&max=200&offset={offset}&status=verified&embed=game,category,players"
        try:
            data = req(url)
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
        url = f"{BASE_URL}/runs?game={game_id}&max=200&offset={offset}&status=verified&embed=game,category,players"
        try:
            print(f"offset: {offset}")
            data = req(url)
            runs.extend(data['data'])

            # Pagination check
            if data['pagination']['size'] < 200:
                break
            offset += 200
        except requests.exceptions.RequestException as e:
            print(f"Error fetching runs: {e}")
            break

    return runs

twitch_url_regex = re.compile(r"https?:\/\/(?:www\.)?twitch\.tv\/\S*", re.IGNORECASE)
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

def process_runs(runs):
    #Extract Twitch highlight urls from runs
    highlights = []
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
                'run_id': run['id']
            }

            if len(player_twitch_yt_urls) != 0:
                highlight["vod_sites"] = player_twitch_yt_urls

            highlights.append(highlight)

    return highlights

def save_highlights(highlights):
    #saving all highlights in a formatted way for the user i guess? My hope is I can automate uploads later
    with open(HIGHLIGHTS_FILE, "w", encoding="utf-8") as f:
        for entry in highlights:
            f.write(f"Players: {', '.join(entry['players'])}\n")
            f.write(f"Category: {entry['category']}\n")
            f.write(f"Time: {str(parse_duration(entry['time']))}\n")
            f.write(f"URL: {' '.join(entry['urls'])}\n")
            f.write(f"Run ID: {entry['run_id']}\n")
            vod_sites = entry.get("vod_sites")
            if vod_sites is not None:
                f.write(f"Vod sites: {' '.join(vod_sites)}\n")

            f.write("-" * 50 + "\n")

    urls = [url for entry in highlights for url in entry["urls"]]
    with open("remaining_downloads.json", "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=4)


def download_videos():
    #downloading videos out of the provided dict using the yt-dlp module.
    ydl_options = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'videos/%(title)s.%(ext)s',
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
            with open("remaining_downloads.json", "r", encoding="utf-8") as f:
                urls = json.load(f)

            # Stop if no URLs are left
            if not urls:
                print("All downloads completed!")
                break

            first_url = urls[0]
            print(f"Downloading: {str(first_url)}")
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                try:
                    ydl.download([first_url])

                except yt_dlp.utils.DownloadError as e:
                    print(f"Skipping invalid or dead link: {first_url} - Error: {e}")
                    urls.pop(0)
                    with open("remaining_downloads.json", "w", encoding="utf-8") as f:
                        json.dump(urls, f, indent=4)
                    continue

                except yt_dlp.utils.ExtractorError as e:
                    #In case you get rate limited. I did. It automatically goes through all downloads in this case and removes the urls unfairly.
                    if "HTTP Error 403: Forbidden" in str(e):
                        print(f"Error: {e}")
                        print("There is a rate limit or some other access restriction (403 Forbidden).")
                        if input("Do you want to stop and resume later? \nYour progress so far has been stored in the remaining_downloads.json (y/n): ").strip().lower().startswith("y"):
                            with open("remaining_downloads.json", "w", encoding="utf-8") as f:
                                json.dump(urls, f, indent=4)
                            print("Progress saved. You can resume the download later.")
                            return  # Exit the function and resume later

                urls.pop(0)
                with open("remaining_downloads.json", "w", encoding="utf-8") as f:
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

def load_remaining_downloads():
    try:
        with open("remaining_downloads.json", "r", encoding="utf-8") as f:
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

def main():
    #Check if there are remaining Downloads left.
    remaininDownloads = load_remaining_downloads()
    if remaininDownloads and input("A remaining downloads file has been found. Do you want to continue the download? (y/n): ").lower().startswith("y"):
        download_videos()
        return

    if input("Do you want to backup a game? If no, this will default to users (y/n): ").lower().startswith("y"):
        print("Enter Speedrun.com Game abbreviation.")
        print("An example, (here in brackets) would be: speedrun.com/[sm64]. The abbreviation would be sm64")
        game = input("Enter Speedrun.com Game abbreviation: ").strip()
        print(f"Searching for {game}...")
        game_id = get_game_id(game)
        print(f"Getting all runs")
        runs = get_all_runs_from_game(game_id)
    else:
        username = input("Enter Speedrun.com username: ").strip()
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

    # Checking for highlights
    highlights = process_runs(runs)
    print(f"Found {len(highlights)} Twitch highlights")

    # Save highlights
    save_highlights(highlights)
    print(f"Saved highlights to {HIGHLIGHTS_FILE}")

    # Download prompt for users and downloading videos
    if highlights and input("Download videos? (y/n): ").lower().startswith("y"):
        download_videos()
        print("Download completed")


if __name__ == "__main__":
    main()
