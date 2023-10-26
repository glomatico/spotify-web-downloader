# Spotify AAC Downloader
A Python script to download songs/albums/playlists directly from Spotify in 256kbps/128kbps AAC.

## Features
* Download songs in 128kbps AAC or 256kbps AAC with a premium account
* Download synced lyrics
* Highly customizable

## Installation
1. Install Python 3.7 or higher
2. Add [FFmpeg](https://ffmpeg.org/download.html) to PATH
    * Older versions of FFmpeg may not work
3. Place your cookies in the same folder that you will run spotify-aac-downloader as `cookies.txt`
    * You can export your cookies by using this Google Chrome extension on Spotify website: https://chrome.google.com/webstore/detail/open-cookiestxt/gdocmgbfkjnnpapoeobnolbbkoibbcif. Make sure to be logged in.
4. Place your .wvd file in the same folder that you will run spotify-aac-downloader as `device.wvd`
    * To get a .wvd file, you can use [dumper](https://github.com/wvdumper/dumper) to dump a L3 CDM from an Android device. Once you have the L3 CDM, use pywidevine to create the .wvd file from it.
        1. Install pywidevine with pip
            ```bash
            pip install pywidevine pyyaml
            ```
        2. Create the .wvd file
            ```bash
            pywidevine create-device -t ANDROID -l 3 -k private_key.pem -c client_id.bin -o .
            ```
5. Install spotify-aac-downloader using pip
    ```bash
    pip install spotify-aac-downloader
    ```

## Examples
* Download a song
    ```bash
    spotify-aac-downloader "https://open.spotify.com/track/18gqCQzqYb0zvurQPlRkpo"
    ```
* Download an album
    ```bash
    spotify-aac-downloader "https://open.spotify.com/album/0r8D5N674HbTXlR3zNxeU1"
    ```

## Configuration
spotify-aac-downloader can be configured using the command line arguments or the config file. The config file is created automatically when you run spotify-aac-downloader for the first time at `~/.spotify-aac-downloader/config.json` on Linux and `%USERPROFILE%\.spotify-aac-downloader\config.json` on Windows. Config file values can be overridden using command line arguments.
| Command line argument / Config file key                         | Description                                                           | Default value                                       |
| --------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------- |
| `-f`, `--final-path` / `final_path`                             | Path where the downloaded files will be saved.                        | `./Spotify`                                         |
| `-t`, `--temp-path` / `temp_path`                               | Path where the temporary files will be saved.                         | `./temp`                                            |
| `-c`, `--cookies-location` / `cookies_location`                 | Location of the cookies file.                                         | `./cookies.txt`                                     |
| `-w`, `--wvd-location` / `wvd_location`                         | Location of the .wvd file.                                            | `./device.wvd`                                      |
| `--config-location` / -                                         | Location of the config file.                                          | `<home_folder>/.spotify-aac-downloader/config.json` |
| `--ffmpeg-location` / `ffmpeg_location`                         | Location of the FFmpeg binary.                                        | `ffmpeg`                                            |
| `--aria2c-location` / `aria2c_location`                         | Location of the aria2c binary.                                        | `aria2c`                                            |
| `--template-folder-album` / `template_folder_album`             | Template of the album folders as a format string.                     | `{album_artist}/{album}`                            |
| `--template-folder-compilation` / `template_folder_compilation` | Template of the compilation album folders as a format string.         | `Compilations/{album}`                              |
| `--template-file-single-disc` / `template_file_single_disc`     | Template of the song files for single-disc albums as a format string. | `{track:02d} {title}`                               |
| `--template-file-multi-disc` / `template_file_multi_disc`       | Template of the song files for multi-disc albums as a format string.  | `{disc}-{track:02d} {title}`                        |
| `--download-mode` / `download_mode`                             | Download mode.                                                        | `ytdlp`                                             |
| `-e`, `--exclude-tags` / `exclude_tags`                         | List of tags to exclude from file tagging separated by commas.        | `null`                                              |
| `--truncate` / `truncate`                                       | Maximum length of the file/folder names.                              | `40`                                                |
| `-l`, `--log-level` / `log_level`                               | Log level.                                                            | `INFO`                                              |
| `-p`, `--premium-quality` / `premium_quality`                   | Download in 256kbps AAC instead of 128kbps AAC.                       | `false`                                             |
| `-l`, `--lrc-only` / `lrc_only`                                 | Download only the synced lyrics.                                      | `false`                                             |
| `-n`, `--no-lrc` / `no_lrc`                                     | Don't download the synced lyrics.                                     | `false`                                             |
| `-s`, `--save-cover` / `save_cover`                             | Save cover as a separate file.                                        | `false`                                             |
| `-o`, `--overwrite` / `overwrite`                               | Overwrite existing files.                                             | `false`                                             |
| `--print-exceptions` / `print_exceptions`                       | Print exceptions.                                                     | `false`                                             |
| `-u`, `--url-txt` / -                                           | Read URLs as location of text files containing URLs.                  | `false`                                             |
| `-n`, `--no-config-file` / -                                    | Don't use the config file.                                            | `false`                                             |

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

### Download mode
The following download modes are available:
* `ytdlp`
* `aria2c`
    * Faster than `ytdlp`
    * Can be obtained from here: https://github.com/aria2/aria2/releases
