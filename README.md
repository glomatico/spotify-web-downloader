# Spotify Web Downloader
A Python script to download songs/music videos/albums/playlists directly from Spotify.

## Features
* Download songs in 128kbps AAC or in 256kbps AAC with a premium account
* Download music videos with a premium account
* Download synced lyrics
* Highly configurable

## Pre-requisites
* The cookies file of your Spotify account (free or premium)
    * You can get your cookies by using this Google Chrome extension on Spotify website: https://chrome.google.com/webstore/detail/open-cookiestxt/gdocmgbfkjnnpapoeobnolbbkoibbcif. Make sure to be logged in.
* FFmpeg on your system PATH
    * Older versions of FFmpeg may not work.
* Python 3.7 or higher

## Installation
1. Install the package `spotify-web-downloader` using pip
    ```bash
    pip install spotify-web-downloader
    ```
2. Place your cookies in the same directory you will run the script from and name it `cookies.txt`

## Usage
* Download a song
    ```bash
    spotify-web-downloader "https://open.spotify.com/track/18gqCQzqYb0zvurQPlRkpo"
    ```
* Download an album
    ```bash
    spotify-web-downloader "https://open.spotify.com/album/0r8D5N674HbTXlR3zNxeU1"
    ```

## Configuration
spotify-web-downloader can be configured using the command line arguments or the config file. The config file is created automatically when you run spotify-web-downloader for the first time at `~/.spotify-web-downloader/config.json` on Linux and `%USERPROFILE%\.spotify-web-downloader\config.json` on Windows. Config file values can be overridden using command line arguments.
| Command line argument / Config file key                         | Description                                                                  | Default value                                |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------- |
| `--download-music-video` / `download_music_video`               | Attempt to download music videos from songs (can lead to incorrect results). | `false`                                      |
| `--save-cover`, `-s` / `save_cover`                             | Save cover as a separate file.                                               | `false`                                      |
| `--overwrite` / `overwrite`                                     | Overwrite existing files.                                                    | `false`                                      |
| `--read-urls-as-txt`, `-r` / -                                  | Interpret URLs as paths to text files containing URLs.                       | `false`                                      |
| `--lrc-only`, `-l` / `lrc_only`                                 | Download only the synced lyrics.                                             | `false`                                      |
| `--no-lrc` / `no_lrc`                                           | Don't download the synced lyrics.                                            | `false`                                      |
| `--config-path` / -                                             | Path to config file.                                                         | `<home>/.spotify-web-downloader/config.json` |
| `--log-level` / `log_level`                                     | Log level.                                                                   | `INFO`                                       |
| `--print-exceptions` / `print_exceptions`                       | Print exceptions.                                                            | `false`                                      |
| `--cookies-path`, `-c` / `cookies_path`                         | Path to .txt cookies file.                                                   | `./cookies.txt`                              |
| `--output-path`, `-o` / `output_path`                           | Path to output directory.                                                    | `./Spotify`                                  |
| `--temp-path` / `temp_path`                                     | Path to temporary directory.                                                 | `./temp`                                     |
| `--wvd-path` / `wvd_path`                                       | Path to .wvd file.                                                           | `null`                                       |
| `--ffmpeg-path` / `ffmpeg_path`                                 | Path to FFmpeg binary.                                                       | `ffmpeg`                                     |
| `--aria2c-path` / `aria2c_path`                                 | Path to aria2c binary.                                                       | `aria2c`                                     |
| `--nm3u8dlre-path` / `nm3u8dlre_path`                           | Path to N_m3u8DL-RE binary.                                                  | `N_m3u8DL-RE`                                |
| `--date-tag-template` / `date_tag_template`                     | Date tag template.                                                           | `%Y-%m-%dT%H:%M:%SZ`                         |
| `--exclude-tags` / `exclude_tags`                               | Comma-separated tags to exclude.                                             | `null`                                       |
| `--truncate` / `truncate`                                       | Maximum length of the file/folder names.                                     | `40`                                         |
| `--template-folder-album` / `template_folder_album`             | Template of the album folders as a format string.                            | `{album_artist}/{album}`                     |
| `--template-folder-compilation` / `template_folder_compilation` | Template of the compilation album folders as a format string.                | `Compilations/{album}`                       |
| `--template-file-single-disc` / `template_file_single_disc`     | Template of the song files for single-disc albums as a format string.        | `{track:02d} {title}`                        |
| `--template-file-multi-disc` / `template_file_multi_disc`       | Template of the song files for multi-disc albums as a format string.         | `{disc}-{track:02d} {title}`                 |
| `--download-mode-song` / `download_mode_song`                   | Download mode for songs.                                                     | `ytdlp`                                      |
| `--premium-quality`, `-p` / `premium_quality`                   | Download songs in premium quality.                                           | `false`                                      |
| `--template-folder-music-video` / `template_folder_music_video` | Template of the music video folders as a format string.                      | `{artist}/Unknown Album`                     |
| `--template-file-music-video` / `template_file_music_video`     | Template of the music video files as a format string.                        | `{title}`                                    |
| `--download-mode-video` / `download_mode_video`                 | Download mode for videos.                                                    | `ydlp`                                       |
| `--no-config-file`, `-n` / -                                    | Do not use a config file.                                                    | `false`                                      |

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
- `producer`
- `rating`
- `release_date`
- `release_year`
- `title`
- `track`
- `track_total`
- `url`

### Music videos quality
Music videos will be downloaded in the highest quality available in H.264/AAC, up to 1080p.

### Download mode
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
