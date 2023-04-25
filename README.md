# Spotify ✨ AAC ✨ Downloader
A Python script to download songs/albums/playlists directly from Spotify in 256kbps/128kbps AAC.

## Setup
1. Install Python 3.7 or newer
2. Install spotify-aac-downloader with pip
    ```
    pip install spotify-aac-downloader
    ```
3. Add FFMPEG to your PATH. You can get it from here: https://ffmpeg.org/download.html
    * If you are on Windows you can move the ffmpeg.exe file to the same folder that you will run the script instead of adding it to your PATH.
4. Export your Spotify cookies as `cookies.txt` to the same folder that you will run the script
    * You can export your cookies by using this Google Chrome extension on Spotify website: https://chrome.google.com/webstore/detail/open-cookiestxt/gdocmgbfkjnnpapoeobnolbbkoibbcif. Make sure to be logged in.
5. Put your Widevine Device file (.wvd) in the same folder that you will run the script
    * You can use Dumper to dump your phone's L3 CDM: https://github.com/Diazole/dumper. Once you have the L3 CDM, you can use pywidevine to create the .wvd file from it.
        1. Install pywidevine with pip
            ```
            pip install pywidevine pyyaml
            ```
        2. Create the .wvd file
            ```
            pywidevine create-device -t ANDROID -l 3 -k private_key.pem -c client_id.bin -o .
            ```

## Usage
```
usage: spotify-aac-downloader [-h] [-u [URLS_TXT]] [-f FINAL_PATH] [-t TEMP_PATH] [-c COOKIES_LOCATION] [-w WVD_LOCATION] [-n]
                   [-p] [-o] [-s] [-e] [-v]
                   [<url> ...]

Download songs/albums/playlists directly from Spotify in AAC

positional arguments:
  <url>                 Spotify song/album/playlist URL(s) (default: None)

options:
  -h, --help            show this help message and exit
  -u [URLS_TXT], --urls-txt [URLS_TXT]
                        Read URLs from a text file (default: None)
  -f FINAL_PATH, --final-path FINAL_PATH
                        Final Path (default: Spotify)
  -t TEMP_PATH, --temp-path TEMP_PATH
                        Temp Path (default: temp)
  -c COOKIES_LOCATION, --cookies-location COOKIES_LOCATION
                        Cookies location (default: cookies.txt)
  -w WVD_LOCATION, --wvd-location WVD_LOCATION
                        .wvd file location (default: *.wvd)
  -n, --no-lrc          Don't create .lrc file (default: False)
  -p, --premium-quality
                        Download 256kbps AAC instead of 128kbps AAC (default: False)
  -o, --overwrite       Overwrite existing files (default: False)
  -s, --skip-cleanup    Skip cleanup (default: False)
  -e, --print-exceptions
                        Print execeptions (default: False)
  -v, --version         show program's version number and exit
```
