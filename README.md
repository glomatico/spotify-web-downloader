# Spotify Web Downloader
A Python CLI app for downloading songs and music videos directly from Spotify.

**Discord Server:** https://discord.gg/aBjMEZ9tnq

## Features
* Download songs in AAC 128kbps or in AAC 256kbps with a premium account
* Download synced lyrics
* Download music videos with a premium account
* Highly configurable

## Prerequisites
* Python 3.8 or higher
* A .wvd file
    * A .wvd file contains the Widevine keys from a device and is required to decrypt the files. The easiest method of obtaining one is using KeyDive, which extracts it from an Android device. Detailed instructions can be found here: https://github.com/hyugogirubato/KeyDive.
    * .wvd files extracted from emulated devices may not work.
* The cookies file of your Spotify browser session in Netscape format (free or premium)
    * You can get your cookies by using one of the following extensions on your browser of choice at the Spotify website with your account signed in:
        * Firefox: https://addons.mozilla.org/addon/export-cookies-txt
        * Chromium based browsers: https://chrome.google.com/webstore/detail/gdocmgbfkjnnpapoeobnolbbkoibbcif
* FFmpeg on your system PATH
    * Older versions of FFmpeg may not work.
    * Up to date binaries can be obtained from the links below:
        * Windows: https://github.com/AnimMouse/ffmpeg-stable-autobuild/releases
        * Linux: https://johnvansickle.com/ffmpeg/

## Installation
1. Install the package `spotify-web-downloader` using pip
    ```bash
    pip install spotify-web-downloader
    ```
2. Place your cookies file and the .wvd file in the directory from which you will be running spotify-web-downloader and name it `cookies.txt` and `device.wvd` respectively.

## Usage
```bash
spotify-web-downloader [OPTIONS] URLS...
```

### Examples
* Download a song
    ```bash
    spotify-web-downloader "https://open.spotify.com/track/18gqCQzqYb0zvurQPlRkpo"
    ```
* Download an album
    ```bash
    spotify-web-downloader "https://open.spotify.com/album/0r8D5N674HbTXlR3zNxeU1"
    ```

## Configuration
spotify-web-downloader can be configured using the command line arguments or the config file.

The config file is created automatically when you run spotify-web-downloader for the first time at `~/.spotify-web-downloader/config.json` on Linux and `%USERPROFILE%\.spotify-web-downloader\config.json` on Windows.

Config file values can be overridden using command line arguments.
| Command line argument / Config file key                         | Description                                                                  | Default value                                  |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------- |
| `--wait-interval`, `-w` / `wait_interval`                       | Wait interval between downloads in seconds.                                  | `10`                                           |
| `--download-music-video` / `download_music_video`               | Attempt to download music videos from songs (can lead to incorrect results). | `false`                                        |
| `--force-premium`, `-f` / `force_premium`                       | Force to detect the account as premium.                                      | `false`                                        |
| `--save-cover`, `-s` / `save_cover`                             | Save cover as a separate file.                                               | `false`                                        |
| `--overwrite` / `overwrite`                                     | Overwrite existing files.                                                    | `false`                                        |
| `--read-urls-as-txt`, `-r` / -                                  | Interpret URLs as paths to text files containing URLs.                       | `false`                                        |
| `--save-playlist` / `save_playlist`                             | Save a M3U8 playlist file when downloading a playlist.                       | `false`                                        |
| `--lrc-only`, `-l` / `lrc_only`                                 | Download only the synced lyrics.                                             | `false`                                        |
| `--no-lrc` / `no_lrc`                                           | Don't download the synced lyrics.                                            | `false`                                        |
| `--config-path` / -                                             | Path to config file.                                                         | `<home>/.spotify-web-downloader/config.json`   |
| `--log-level` / `log_level`                                     | Log level.                                                                   | `INFO`                                         |
| `--print-exceptions` / `print_exceptions`                       | Print exceptions.                                                            | `false`                                        |
| `--cookies-path`, `-c` / `cookies_path`                         | Path to .txt cookies file.                                                   | `./cookies.txt`                                |
| `--output-path`, `-o` / `output_path`                           | Path to output directory.                                                    | `./Spotify`                                    |
| `--temp-path` / `temp_path`                                     | Path to temporary directory.                                                 | `./temp`                                       |
| `--wvd-path` / `wvd_path`                                       | Path to .wvd file.                                                           | `./device.wvd`                                 |
| `--ffmpeg-path` / `ffmpeg_path`                                 | Path to FFmpeg binary.                                                       | `ffmpeg`                                       |
| `--mp4box-path` / `mp4box_path`                                 | Path to MP4Box binary.                                                       | `MP4Box`                                       |
| `--mp4decrypt-path` / `mp4decrypt_path`                         | Path to mp4decrypt binary.                                                   | `mp4decrypt`                                   |
| `--aria2c-path` / `aria2c_path`                                 | Path to aria2c binary.                                                       | `aria2c`                                       |
| `--nm3u8dlre-path` / `nm3u8dlre_path`                           | Path to N_m3u8DL-RE binary.                                                  | `N_m3u8DL-RE`                                  |
| `--remux-mode` / `remux_mode`                                   | Remux mode.                                                                  | `ffmpeg`                                       |
| `--template-folder-album` / `template_folder_album`             | Template folder for tracks that are part of an album.                        | `{album_artist}/{album}`                       |
| `--template-folder-compilation` / `template_folder_compilation` | Template folder for tracks that are part of a compilation album.             | `Compilations/{album}`                         |
| `--template-file-single-disc` / `template_file_single_disc`     | Template file for the tracks that are part of a single-disc album.           | `{track:02d} {title}`                          |
| `--template-file-multi-disc` / `template_file_multi_disc`       | Template file for the tracks that are part of a multi-disc album.            | `{disc}-{track:02d} {title}`                   |
| `--template-folder-no-album` / `template_folder_no_album`       | Template folder for the tracks that are not part of an album.                | `{artist}/Unknown Album`                       |
| `--template-file-no-album` / `template_file_no_album`           | Template file for the tracks that are not part of an album.                  | `{title}`                                      |
| `--template-file-playlist` / `template_file_playlist`           | Template file for the M3U8 playlist.                                         | `Playlists/{playlist_artist}/{playlist_title}` |
| `--date-tag-template` / `date_tag_template`                     | Date tag template.                                                           | `%Y-%m-%dT%H:%M:%SZ`                           |
| `--exclude-tags` / `exclude_tags`                               | Comma-separated tags to exclude.                                             | `null`                                         |
| `--truncate` / `truncate`                                       | Maximum length of the file/folder names.                                     | `null`                                         |
| `--download-mode-song` / `download_mode_song`                   | Download mode for songs.                                                     | `ytdlp`                                        |
| `--premium-quality`, `-p` / `premium_quality`                   | Download songs in premium quality.                                           | `false`                                        |
| `--download-mode-video` / `download_mode_video`                 | Download mode for videos.                                                    | `ytdlp`                                        |
| `--no-config-file`, `-n` / -                                    | Do not use a config file.                                                    | `false`                                        |



### Tag variables
The following variables can be used in the template folder/file and/or in the `exclude_tags` list:
- `album`
- `album_artist`
- `artist`
- `compilation`
- `composer`
- `copyright`
- `cover`
- `disc`
- `disc_total`
- `isrc`
- `label`
- `lyrics`
- `media_type`
- `playlist_artist`
- `playlist_title`
- `playlist_track`
- `producer`
- `rating`
- `release_date`
- `release_year`
- `title`
- `track`
- `track_total`
- `url`
  
### Remux modes
The following remux modes are available:
* `ffmpeg`
* `mp4box`
    * Requires mp4decrypt
    * Can be obtained from here: https://gpac.wp.imt.fr/downloads

### Music videos quality
Music videos will be downloaded in the highest quality available in H.264/AAC, up to 1080p.

### Download modes
The following modes are available for songs:
* `ytdlp`
* `aria2c`
    * Faster than `ytdlp`
    * Can be obtained from here: https://github.com/aria2/aria2/releases

The following modes are available for videos:
* `ytdlp`
* `nm3u8dlre`
    * Faster than `ytdlp`
    * Can be obtained from here: https://github.com/nilaoda/N_m3u8DL-RE/releases
