# Spotify Web Downloader
A Python script to download songs/music videos/albums/playlists directly from Spotify.

## Features
* Download songs in 128kbps AAC or in 256kbps AAC with a premium account
* Download music videos with a premium account
* Download synced lyrics
* Highly configurable

## Installation
1. Install Python 3.7 or higher
2. Add [FFmpeg](https://ffmpeg.org/download.html) to your system PATH
    * Older versions of FFmpeg may not work
3. Place your cookies in the same folder that you will run spotify-web-downloader as `cookies.txt`
    * You can export your cookies by using this Google Chrome extension on Spotify website: https://chrome.google.com/webstore/detail/open-cookiestxt/gdocmgbfkjnnpapoeobnolbbkoibbcif. Make sure to be logged in.
4. Install spotify-web-downloader using pip
    ```bash
    pip install spotify-web-downloader
    ```

## Examples
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
| Command line argument / Config file key                         | Description                                                           | Default value                                     |
| --------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------- |
| `-s,`, `--save-cover` / `save_cover`                            | Save cover as a separate file.                                        | `false`                                           |
| `--overwrite` / `overwrite`                                     | Overwrite existing files.                                             | `false`                                           |
| `-r,`, `--read-urls-as-txt` / -                                 | Interpret URLs as paths to text files containing URLs.                | `false`                                           |
| `-l,`, `--lrc-only` / `lrc_only`                                | Download only the synced lyrics.                                      | `false`                                           |
| `-n,`, `--no-lrc` / `no_lrc`                                    | Don't download the synced lyrics.                                     | `false`                                           |
| `--config-path` / -                                             | Path to config file.                                                  | `<home_path>/.spotify-web-downloader/config.json` |
| `--log-level` / `log_level`                                     | Log level.                                                            | `INFO`                                            |
| `--print-exceptions` / `print_exceptions`                       | Print exceptions.                                                     | `false`                                           |
| `-c,`, `--cookies-path` / `cookies_path`                        | Path to .txt cookies file                                             | `cookies.txt`                                     |
| `-o,`, `--output-path` / `output_path`                          | Path to output directory                                              | `Spotify`                                         |
| `--temp-path` / `temp_path`                                     | Path to temporary directory                                           | `temp`                                            |
| `--wvd-path` / `wvd_path`                                       | Path to .wvd file                                                     | `null`                                            |
| `--ffmpeg-path` / `ffmpeg_path`                                 | Path to ffmpeg binary                                                 | `ffmpeg`                                          |
| `--aria2c-path` / `aria2c_path`                                 | Path to aria2c binary                                                 | `aria2c`                                          |
| `--nm3u8dlre-path` / `nm3u8dlre_path`                           | Path to nm3u8dlre binary                                              | `N_m3u8DL-RE`                                     |
| `--date-tag-template` / `date_tag_template`                     | Date tag template                                                     | `%Y-%m-%dT%H:%M:%SZ`                              |
| `--exclude-tags` / `exclude_tags`                               | Comma-separated tags to exclude                                       | `null`                                            |
| `--truncate` / `truncate`                                       | Maximum length of the file/folder names.                              | `40`                                              |
| `--template-folder-album` / `template_folder_album`             | Template of the album folders as a format string.                     | `{album_artist}/{album}`                          |
| `--template-folder-compilation` / `template_folder_compilation` | Template of the compilation album folders as a format string.         | `Compilations/{album}`                            |
| `--template-file-single-disc` / `template_file_single_disc`     | Template of the song files for single-disc albums as a format string. | `{track:02d} {title}`                             |
| `--template-file-multi-disc` / `template_file_multi_disc`       | Template of the song files for multi-disc albums as a format string.  | `{disc}-{track:02d} {title}`                      |
| `--download-mode-song` / `download_mode_song`                   | Download mode for songs.                                              | `ytdlp`                                           |
| `-p,`, `--premium-quality` / `premium_quality`                  | Download songs in premium quality.                                    | `false`                                           |
| `--template-folder-music-video` / `template_folder_music_video` | Template of the music video folders as a format string.               | `{artist}/Unknown Album`                          |
| `--template-file-music-video` / `template_file_music_video`     | Template of the music video files as a format string.                 | `{title}`                                         |
| `--download-mode-video` / `download_mode_video`                 | Download mode for videos.                                             | `ytdlp`                                           |
| `-n,`, `--no-config-file` / -                                   | Do not use a config file.                                             | `false`                                           |



### Tag variables
The following variables can be used in the template folder/file and/or in the `exclude_tags` list:
- `album`
- `album_artist`
- `artist`
- `comment`
- `compilation`
- `copyright`
- `cover`
- `disc`
- `disc_total`
- `isrc`
- `label`
- `lyrics`
- `media_type`
- `rating`
- `release_date`
- `title`
- `track`
- `track_total`

### Music videos quality
Music videos will be downloaded in the highest quality available, up to 1080p.

### Download mode

#### Songs
The following modes are available:
* `ytdlp`
* `aria2c`
    * Faster than `ytdlp`
    * Can be obtained from here: https://github.com/aria2/aria2/releases

#### Videos
The following modes are available:
* `ytdlp`
* `nm38dlre`
    * Faster than `ytdlp`
    * Can be obtained from here: https://github.com/nilaoda/N_m3u8DL-RE/releases
