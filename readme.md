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
```sh
pip install -r requirements.txt
```
4. Make sure to have ffmpeg installed. This script is using yt-dlp which absolutely requires ffmpeg. Look for an installation guide for installing ffmpeg. You can download it here on [their official website](https://ffmpeg.org/download.html)

To run the script, run `python speedrunrescue.py`. Please read the [configuration options](#configuration) below.

## Configuration
Options to the program are provided in a file called `config.yml`, in the same folder as the script (For executable users, do not worry, where config.yml is placed is correct).

Telling the program what to do is very simple. The program is controlled by options, which dictates one aspect of what the program should do.

### Specifying an option
To specify an option:
1. Find an empty line to place the option.
2. Place the option name, e.g. `username`, followed by a colon and a space (`: `), followed by the option value, e.g. `luckytyphlosion`.

For this example, the full option would be:
```
username: luckytyphlosion
```

You should not list the same option multiple times. For example, **do not** do this:
```
username: luckytyphlosion
username: Matse007
```

This is important as in the pre-made `config.yml` in the executable release, some options have already been specified, so you should not add multiple of the option.

### Ignoring an option
Sometimes, you may to ignore an option in your configuration. There are two ways to do this.
1. Add a `#` at the start of the option. For example, `#username: luckytyphlosion`
2. Remove the option entirely by deleting the line.

## Tasks
There are two ways of editing `config.yml`, depending on your purposes. These two are explained below.

### Downloading from a speedrun.com user
1. [Ignore](#ignoring-an-option) the `game` option if it is there and not ignored already. 
2. [Specify](#specifying-an-option) an option called `username`. The value should be the speedrun.com username for which you want to download runs from.
3. Optionally, you can [specify](#specifying-an-option) the option `video-folder-name`, which will control the folder where your videos are stored. You can get the folder name by double clicking the address bar in Windows Explorer of the folder you want. Note that you must use forward slashes as path separators, e.g. `D:\speedrunrescuescript\videos` must become `D:/speedrunrescuescript/videos`. If you aren't sure, leave it as `videos`.
4. [Ignore](#ignoring-an-option) the `app-id` and `app-secret` options if they exist.
5. [Specify](#specifying-an-option) the `download-videos` option, by putting `true` if you want to fetch information about the user's runs and download the videos, or `false` if you only want to fetch the information.
6. Optionally, you can [specify](#specifying-an-option) a video quality target using the `video-quality` option. The value should either be the video quality or the video height which you want to target, e.g. `"360p"`, `"720"`, `"1080p"`, `"542"`. It can also be `"best"`, which will just automatically download the highest quality video. The program will default to `"best"` is this option is omitted. **THIS OPTION SHOULD BE IN QUOTES**, i.e. do `"360p"`, not `360p`. In case the specified quality cannot be found, the program will try to find an adjacent quality and download that. Add `>=` before the quality to download the closest higher quality, e.g. `">=480p"`, and `>=` to download the closest lower quality, e.g. `"<=480p"`. If neither are specified, the program assumes `>=` is chosen. For example, if a video has the quality options 360p and 542p, this is the logic of `>=` and `<=`:
    - `>=480p`: Will download 542p, as it is the next higher quality
    - `<=480p`: Will download 360p, as it is the next lower quality

    Sometimes, the lower quality encodes Twitch produces are greater in size than the lower quality resolutions (e.g. viewing the sizes of [this video](https://www.twitch.tv/videos/1906117644) using [TwitchDownloader](https://github.com/lay295/TwitchDownloader) says that the Source resolution is smaller than 480p). After deciding the desired quality, the program will check if this is the case, and download the Source quality if it is smaller than the initial desired quality.
7. [Specify](#specifying-an-option) the `ignore-links-in-description` option with `true` if want to ignore video links that are posted in the run description and only check video links in the submission field, and `false` if you want to check links from both the submission field and the description. Not recommended as some people put other parts of the run in the description.

Here is an example config that will download twitch runs from [speedrun.com user luckytyphlosion](https://speedrun.com/users/luckytyphlosion).
```yaml
# Specify either a game or a speedrun.com username
username: "luckytyphlosion"
# The output folder of the videos. Stored on a separate drive in this example
video-folder-name: D:/speedrunrescuescript/videos
# Whether to download the videos or just look at the output
download-videos: true
#specify the desired videoquality ranges from 160 - 1080. Can be left empty, it will default to the best quality.
video-quality: ">=1080p"
#specify if you explicitly want to ignore links that are posted in the run description and only check submission videos.
ignore-links-in-description: false
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
1. [Ignore](#ignoring-an-option) the `username` option if it is there and not ignored already. 
2. [Specify](#specifying-an-option) an option called `game`. The value should be the speedrun.com game abbreviation of the leaderboard you want to download. You can find the abbreviation in the url of a leaderboard, after `speedrun.com`. For example, the abbreviation of https://speedrun.com/sm64 is `sm64`.
3. Optionally, you can [specify](#specifying-an-option) the option `video-folder-name`, which will control the folder where your videos are stored. You can get the folder name by double clicking the address bar in Windows Explorer of the folder you want. Note that you must use forward slashes as path separators, e.g. `D:\speedrunrescuescript\videos` must become `D:/speedrunrescuescript/videos`. If you aren't sure, leave it as `videos`.
4. [Specify](#ignoring-an-option) the `app-id` option. The value should be the **Client ID** which you saved earlier.
5. [Specify](#ignoring-an-option) the `app-secret` option. The value should be the **Client Secret** which you saved earlier.
6. [Specify](#specifying-an-option) the `download-videos` option, by putting `true` if you want to fetch information about the user's runs and download the videos, or `false` if you only want to fetch the information.
7. [Specify](#specifying-an-option) the `allow-all` option. This should be `false` if you only want to download videos of channels who have not reached the 100h limit, or `true` if you want to download all runs regardless.
8. Optionally, you can [specify](#specifying-an-option) a video quality target using the `video-quality` option. The value should either be the video quality or the video height which you want to target, e.g. `"360p"`, `"720"`, `"1080p"`, `"542"`. It can also be `"best"`, which will just automatically download the highest quality video. The program will default to `"best"` is this option is omitted. **THIS OPTION SHOULD BE IN QUOTES**, i.e. do `"360p"`, not `360p`. In case the specified quality cannot be found, the program will try to find an adjacent quality and download that. Add `>=` before the quality to download the closest higher quality, e.g. `">=480p"`, and `>=` to download the closest lower quality, e.g. `"<=480p"`. If neither are specified, the program assumes `>=` is chosen. For example, if a video has the quality options 360p and 542p, this is the logic of `>=` and `<=`:
    - `>=480p`: Will download 542p, as it is the next higher quality
    - `<=480p`: Will download 360p, as it is the next lower quality

    Sometimes, the lower quality encodes Twitch produces are greater in size than the lower quality resolutions (e.g. viewing the sizes of [this video](https://www.twitch.tv/videos/1906117644) using [TwitchDownloader](https://github.com/lay295/TwitchDownloader) says that the Source resolution is smaller than 480p). After deciding the desired quality, the program will check if this is the case, and download the Source quality if it is smaller than the initial desired quality.
9. [Specify](#specifying-an-option) the `ignore-links-in-description` option with `true` if want to ignore video links that are posted in the run description and only check video links in the submission field, and `false` if you want to check links from both the submission field and the description. Not recommended as some people put other parts of the run in the description.
10. Optionally you can [specify](#specifying-an-option) the `concurrent-fragments` option with a postive integer of how many video fragments you want to download concurrently. Note that this will create the specified number of threads so if your system can't handle this leave this at 1.

Here is an example config that will download twitch runs from [the speedrun.com leaderboard for Rockman EXE 4.5: Real Operation](https://speedrun.com/mmbn4.5).
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
#specify the desired videoquality ranges from 160 - 1080. Can be left empty, it will default to the best quality.
video-quality: ">=1080p"
#specify if you explicitly want to ignore links that are posted in the run description and only check submission videos.
ignore-links-in-description: false
```

## Additional filtering
If `download-videos` is `false`, you can edit the list of files that would be downloaded. For downloading user runs, the relevant files are in `output/user/<username>`. For downloading leaderboard runs, the relevant files are in `output/game/<game>`.

You can delete lines in `remaining_downloads.json` to omit downloading certain files. This can be useful if you want to avoid downloading runs which you know have a mirror elsewhere. Note that if you choose not to process the "remaining downloads file", this file will be overwritten, so please keep a backup somewhere.

## Errors
Q: I'm getting outdated information from speedrun.com/Twitch. How do I fix this?

A: To get updated information from speedrun.com, delete the folder named `srcom_cached`. To get updated information from Twitch, delete the file named `twitch_cache.json`. It is recommended to do this infrequently in order to save time by not issuing requests for information which is mostly up-to-date.
