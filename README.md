# Spotify ✨ AAC ✨ Downloader
A Python script to download songs/albums/playlists directly from Spotify in 256kbps/128kbps AAC following the iTunes standard.

## Setup
1. Install Python 3.8 or higher
2. Install the required packages using pip: 
    ```
    pip install -r requirements.txt
    ```
3. Add MP4Box and mp4decrypt to your PATH
    * You can get them from here:
        * MP4Box: https://gpac.wp.imt.fr/downloads/
        * mp4decrypt: https://www.bento4.com/downloads/
4. Export your Spotify cookies as `cookies.txt` and put it in the same folder as the script
    * You can export your cookies by using this Google Chrome extension on Spotify website with your account logged in: https://chrome.google.com/webstore/detail/gdocmgbfkjnnpapoeobnolbbkoibbcif. Make sure to export it as `cookies.txt` to the same directory as the script or specify the location using `--cookies-location` argument.
5. Put your L3 Widevine Keys (`device_client_id_blob` and `device_private_key` files) on `./pywidevine/L3/cdm/devices/android_generic` folder
    * You can get your L3 Widevine Keys by using Dumper: https://github.com/Diazole/dumper
        * The generated `private_key.pem` and `client_id.bin` files should be renamed to `device_private_key` and `device_client_id_blob` respectively.

## Usage
```
python spotiy_aac_downloader.py [OPTIONS] [URLS]
```
Tracks are saved in `./Spotify` by default, but the directory can be changed using `--final-path` argument.

By default, the script will download songs in 128kbps AAC. Use `--premium-quality` argument if you have a premium account and want to download songs in 256kbps AAC.

Use `--help` argument to see all available options.
