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
    with open("remaining_downloads.json", "w", encoding="utf-8") as f:
        json.dump([entry['url'] for entry in highlights], f, indent=4)


def download_videos():
    #downloading videos out of the provided dict using the yt-dlp module.
    ydl_options = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'videos/%(title)s.%(ext)s',
        'noplaylist': True,

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
            print(f"Downloading: {first_url}")
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                ydl.download([first_url])
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
            break

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
