# Speedrun.com Twitch Highlight Downloader
With the [recent changes to Twitch highlights](https://x.com/twitchsupport/status/1892277199497043994) which limit the total duration of highlights for a channel to 100 hours, there has been significant panic about the loss of Twitch VODs on speedrun.com. This program aims to assist in archiving Twitch VODs, by providing the following functions:
- Finding all runs submitted by a user OR all runs on a game leaderboard, that are hosted on Twitch, and writing that information to a file
- Downloading all runs as described above
  - For runs from a game leaderboard, optionally only downloading runs from channels which have exceeded the highlight limit.

Have any questions? Ask in the [official speedrun.com Discord](https://discord.gg/0h6sul1ZwHVpXJmK).

# Setup (Executable, Windows only)
1. Download the latest release [here](https://github.com/Matse007/SpeedrunRescueScript/releases/latest). Be sure to download the file called "SpeedrunRescueScript_v{xxx}.zip", where {xxx} is the version number.
2. Extract the zip file and open its contents.
3. Run the program by clicking `speedrun_rescue.bat`, **BUT DON'T DO SO YET**. Read the [configuration options](#configuration) first.

# Setup (command line)

## Prerequisites
Before running the script you need to have the following tools installed:  
- Python 3.x which you can download here if you have not yet: https://www.python.org/downloads/
- Install the required Python packages. The script depends on several external libraries. You can install these using pip and the requirements.txt file you find in this project as well.

## Installation Steps
1. Click the Code button on top of the webpage and press download Zip. If you are an advanced user, clone the repository.
2. Unpack the zip file or go into the folder and open a command line. If you are on Windows you can do that by clicking into the Link field in windows explorer and typing in cmd.
3. Install all the dependencies using the following command (copy pasting this into the command prompt)
```pyton
pip install -r requirements.txt
```
4. Make sure to have ffmpeg installed. This script is using yt-dlp which absolutely requires ffmpeg. Look for an installation guide for installing ffmpeg. You can download it here on [their official website](https://ffmpeg.org/download.html)

To run the script, run `python speedrunrescue.py`. Please read the [configuration options](#configuration) below.

## Configuration
Options to the program are provided in a file called `config.yml`, in the same folder as the script (For executable users, do not worry, where config.yml is placed is correct).

There are two ways of editing `config.yml`, depending on your purposes. These two are explained below.

### Downloading from a speedrun.com user
1. Delete the line starting with `game:` in the `config.yml`. If it doesn't exist, ignore this step.
2. Add a line starting with `username:`, and after, add the speedrun.com username of the user you want the runs of in "quotes". If a line starting with `username:` already exists, replace the contents after the line with the speedrun.com username.
3. Optionally, you can add a separate folder name for where the videos will be stored, at `video-folder-name:`. You can get the folder name by double clicking the address bar in Windows Explorer of the folder you want. Note that you must use forward slashes as path separators, e.g. `D:\speedrunrescuescript\videos` must become `D:/speedrunrescuescript/videos`. If you aren't sure, leave it as `videos`. 
4. Delete the lines starting with `app-id` and `app-secret` if they exist. Alternatively, add `#` to the start of the line to comment it out.
5. At the line starting with `download-videos:`, put `true` or `false` to indicate whether you want to download the videos, or just fetch information about the speedrun.com user's runs.

Here is an example config that will download twitch runs from [speedrun.com user luckytyphlosion](https://speedrun.com/users/luckytyphlosion). Note that `#` indicates a comment, i.e. the text will be ignored. You can add your own notes using comments.
```yaml
# Specify either a game or a speedrun.com username
username: "luckytyphlosion"
# The output folder of the videos. Stored on a separate drive in this example
video-folder-name: D:/speedrunrescuescript/videos
# Whether to download the videos or just look at the output
download-videos: true
```

### Downloading from a speedrun.com leaderboard
Before you start, you must set up a Twitch API App. You will only need to do this once. Instructions are provided below. You can also read Twitch's official instructions [here](https://dev.twitch.tv/docs/authentication/register-app/).

#### Setting up a Twitch API App
1. Enable two-factor authentication (2FA) for your account. This is required in order to create apps. To enable 2FA, navigate to [Security and Privacy](https://www.twitch.tv/settings/security), and follow the steps for enabling 2FA under the Security section.
2. Log in to the [developer console](https://dev.twitch.tv/console) using your Twitch account.
3. Select the **Applications** tab on the left side and then click **Register Your Application**.
4. Set the **Name** of your application to anything (I used "Highlight Limit Detector").
5. Set the **OAuth Redirect URLs** to `http://localhost`. Do not click Add.
6. Set the **Category** of your application to something fitting (I used "Analytics")
7. Keep the Client Type as Confidential.
8. Click **Create** to make your app. You may need to solve a Captcha.
9. Back in the **Applications** tab, locate your app under **Developer Applications**, and click **Manage**.
10. Scroll down to the **Client ID** and save the text in the textbox (looks like a random string of characters) for later.
11. Under **Client Secret**, click the **New Secret** button, confirm with **OK**, and then save the text that is shown for later. This will disappear after you leave the page, so be sure to save it somewhere safe.
    * **WARNING: DO NOT SHARE THIS CLIENT SECRET**. Letting it become public can lead to people abusing the API with **YOUR** account, and can possibly lead to you getting banned from Twitch.

#### Setting up the configuration for a speedrun.com leaderboard
1. Delete the line starting with `username:` in the `config.yml`. If it doesn't exist, ignore this step.
2. Add a line starting with `game:`, and after, add the speedrun.com game abbreviation of the leaderboard you want to download. You can find the abbreviation in the url of a leaderboard, after `speedrun.com`. For example, the abbreviation of https://speedrun.com/sm64 is `sm64`. If a line starting with `game:` already exists, replace the contents after the line with the speedrun.com game.
3. Optionally, you can add a separate folder name for where the videos will be stored, at `video-folder-name:`. You can get the folder name by double clicking the address bar in Windows Explorer of the folder you want. Note that you must use forward slashes as path separators, e.g. `D:\speedrunrescuescript\videos` must become `D:/speedrunrescuescript/videos`. If you aren't sure, leave it as `videos`. 
4. At the line starting with `app-id:`, paste the **Client ID** after `app-id:` which you saved earlier.
5. At the line starting with `app-secret:`, paste the **Client Secret** after `app-secret:` which you saved earlier.
6. At the line starting with `download-videos:`, put `true` or `false` to indicate whether you want to download the videos, or just fetch information about the speedrun.com user's runs.
7. By default, the script will only download videos of channels who have not reached the 100h limit. If you want to download all runs irregardless of at-risk status, then add the following line: `allow-all: true`. Otherwise, don't add the line, or add `allow-all: false`.

Here is an example config that will download twitch runs from [the speedrun.com leaderboard for Rockman EXE 4.5: Real Operation](https://speedrun.com/mmbn4.5). Note that `#` indicates a comment, i.e. the text will be ignored. You can add your own notes using comments.
```yaml
# Specify either a game or a speedrun.com username
game: "mmbn4.5"
# The output folder of the videos. Stored on a separate drive in this example
video-folder-name: D:/speedrunrescuescript/videos
# Whether to download the videos or just look at the output
app-id: e3udyluhnly6q6g2qp5a00nwaz73dj
app-secret: n8p6t5qy6f33lnm3v8jjgwliqazps0
download-videos: false
allow-all: false
```

## Additional filtering
If `download-videos` is `false`, you can edit the list of files that would be downloaded. For downloading user runs, the relevant files are in `output/user/<username>`. For downloading leaderboard runs, the relevant files are in `output/game/<game>`.

You can delete lines in `remaining_downloads.json` to omit downloading certain files. This can be useful if you want to avoid downloading runs which you know have a mirror elsewhere. Note that if you choose not to process the "remaining downloads file", this file will be overwritten, so please keep a backup somewhere.

## Errors
Q: I'm getting outdated information from speedrun.com/Twitch. How do I fix this?

A: To get updated information from speedrun.com, delete the folder named `srcom_cached`. To get updated information from Twitch, delete the file named `twitch_cache.json`. It is recommended to do this infrequently in order to save time by not issuing requests for information which is mostly up-to-date.
