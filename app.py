import re
import time
import requests
from urllib.parse import quote
from isodate import parse_duration
import yt_dlp

# Configuration
BASE_URL = "https://www.speedrun.com/api/v1"
RATE_LIMIT = 0.6  # 600ms between requests because rate limits. Something I learned today
DEBUG_FILE = "debug_log.txt"
HIGHLIGHTS_FILE = "twitch_highlights.txt"
timestamp = time.time()

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


def get_all_runs(user_id):
    #gettign all runs with pagination in mind.
    runs = []
    offset = 0

    while True:
        url = f"{BASE_URL}/runs?user={user_id}&max=200&offset={offset}&status=verified&embed=game,category"
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


def is_twitch_url(url):
    # Checking with regex if its a twitch highlight
    pattern = r"https?:\/\/(?:www\.)?twitch\.tv\/\S*"
    return re.match(pattern, url, re.IGNORECASE)


def process_runs(runs):
    #Extract Twitch highlight urls from runs
    highlights = []
    for run in runs:
        videos = run.get('videos') or {}
        links = videos.get('links') or []

        for video in links:
            uri = video.get('uri', '')
            if is_twitch_url(uri):
                highlights.append({
                    'game': run['game']['data']['names']['international'],
                    'category': run['category']['data']['name'],
                    'time': run['times']['primary'],
                    'url': uri,
                    'run_id': run['id']
                })
                break

    return highlights

def save_highlights(highlights):
    #saving all highlights in a formatted way for the user i guess? My hope is I can automate uploads later
    with open(HIGHLIGHTS_FILE, "w", encoding="utf-8") as f:
        for entry in highlights:
            f.write(f"Game: {entry['game']}\n")
            f.write(f"Category: {entry['category']}\n")
            f.write(f"Time: {str(parse_duration(entry['time']))}\n")
            f.write(f"URL: {entry['url']}\n")
            f.write(f"Run ID: {entry['run_id']}\n")
            f.write("-" * 50 + "\n")


def download_videos(highlights):
    #downloading videos out of the provided dict using the yt-dlp module.
    ydl_options = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        for idx, entry in enumerate(highlights, 1):
            print(f"Downloading {idx}/{len(highlights)}: {entry['url']}")
            try:
                ydl.download([entry['url']])
            except yt_dlp.utils.DownloadError as e:
                print(f"Failed to download {entry['url']}: {e}")



def main():
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
        download_videos(highlights)
        print("Download completed")


if __name__ == "__main__":
    main()
