# Speedrun.com Twitch Highlight Downloader
This simple Python Script helps you to check your own runs 
on Speedrun.com and lets you automatically download all twitch highlights that you still have submitted.

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
4. Makesure to have ffmpeg installed. This script is using yt-dlp which absolutely requires ffmpeg. Look for an installation guide for installing ffmpeg. You can download it here on [their official website](https://ffmpeg.org/download.htmltheir)

## How to use this
1. Run the script. Again you need to have a command line open in your local folder as explained above and then by typing this command:
```python
python speedrunrescue.py
```
2. Just follow the instructions from the programm.