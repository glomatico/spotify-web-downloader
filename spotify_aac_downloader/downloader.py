from __future__ import annotations

import datetime
import functools
import re
import shutil
import subprocess
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import base62
import requests
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from pywidevine import PSSH, Cdm, Device
from yt_dlp import YoutubeDL

from .constants import *


class Downloader:
    def __init__(
        self,
        final_path: Path,
        temp_path: Path,
        cookies_location: Path,
        wvd_location: Path,
        ffmpeg_location: str,
        aria2c_location: str,
        template_folder_album: str,
        template_folder_compilation: str,
        template_file_single_disc: str,
        template_file_multi_disc: str,
        exclude_tags: str,
        truncate: int,
        premium_quality: bool,
        **kwargs,
    ):
        self.final_path = final_path
        self.temp_path = temp_path
        self.cookies_location = cookies_location
        self.wvd_location = wvd_location
        self.ffmpeg_location = (
            shutil.which(ffmpeg_location) if ffmpeg_location else None
        )
        self.aria2c_location = (
            shutil.which(aria2c_location) if aria2c_location else None
        )
        self.template_folder_album = template_folder_album
        self.template_folder_compilation = template_folder_compilation
        self.template_file_single_disc = template_file_single_disc
        self.template_file_multi_disc = template_file_multi_disc
        self.exclude_tags = (
            [i.lower() for i in exclude_tags.split(",")]
            if exclude_tags is not None
            else []
        )
        self.truncate = None if truncate < 4 else truncate
        self.audio_quality = "MP4_256" if premium_quality else "MP4_128"

    def setup_session(self) -> None:
        cookies = MozillaCookieJar(self.cookies_location)
        cookies.load(ignore_discard=True, ignore_expires=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "app-platform": "WebPlayer",
                "accept": "application/json",
                "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6,zh;q=0.5,ru;q=0.4,es;q=0.3,ja;q=0.2",
                "content-type": "application/json",
                "origin": "https://open.spotify.com",
                "referer": "https://open.spotify.com/",
                "sec-ch-ua": '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            }
        )
        self.session.cookies.update(cookies)
        home_page = self.session.get("https://open.spotify.com/").text
        token = re.search(r'accessToken":"(.*?)"', home_page).group(1)
        self.is_premium = re.search(r'isPremium":(.*?),', home_page).group(1)
        self.session.headers.update(
            {
                "authorization": f"Bearer {token}",
            }
        )

    def setup_cdm(self) -> None:
        self.cdm = Cdm.from_device(Device.load(self.wvd_location))
        self.cdm_session = self.cdm.open()

    def get_download_queue(self, url: str) -> list[dict]:
        uri = re.search(r"(\w{22})", url).group(1)
        download_queue = []
        if "album" in url:
            download_queue.extend(self.get_album(uri)["tracks"]["items"])
        elif "track" in url:
            download_queue.append(self.get_track(uri))
        elif "playlist" in url:
            download_queue.extend(
                [i["track"] for i in self.get_playlist(uri)["tracks"]["items"]]
            )
        else:
            raise Exception("Not a valid Spotify URL")
        return download_queue

    def uri_to_gid(self, uri: str) -> str:
        return hex(base62.decode(uri, base62.CHARSET_INVERTED))[2:].zfill(32)

    def gid_to_uri(self, gid: str) -> str:
        return base62.encode(int(gid, 16), charset=base62.CHARSET_INVERTED).zfill(22)

    def get_track(self, track_id: str) -> dict:
        return self.session.get(f"https://api.spotify.com/v1/tracks/{track_id}").json()

    @functools.lru_cache()
    def get_album(self, album_id: str) -> dict:
        album = self.session.get(f"https://api.spotify.com/v1/albums/{album_id}").json()
        album_next_url = album["tracks"]["next"]
        while album_next_url is not None:
            album_next = self.session.get(album_next_url).json()
            album["tracks"]["items"].extend(album_next["items"])
            album_next_url = album_next["next"]
        return album

    def get_playlist(self, playlist_id: str) -> dict:
        playlist = self.session.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}"
        ).json()
        playlist_next_url = playlist["tracks"]["next"]
        while playlist_next_url is not None:
            playlist_next = self.session.get(playlist_next_url).json()
            playlist["tracks"]["items"].extend(playlist_next["items"])
            playlist_next_url = playlist_next["next"]
        return playlist

    def get_metadata(self, gid: str) -> dict:
        return self.session.get(
            f"https://spclient.wg.spotify.com/metadata/4/track/{gid}?market=from_token"
        ).json()

    def get_file_id(self, metadata: dict) -> str:
        audio_files = metadata.get("file")
        if audio_files is None:
            if metadata.get("alternative") is not None:
                audio_files = metadata["alternative"][0]["file"]
            else:
                return None
        return next(
            i["file_id"] for i in audio_files if i["format"] == self.audio_quality
        )

    def get_pssh(self, file_id: str) -> str:
        return requests.get(
            f"https://seektables.scdn.co/seektable/{file_id}.json"
        ).json()["pssh"]

    def get_decryption_key(self, pssh: str) -> str:
        pssh = PSSH(pssh)
        challenge = self.cdm.get_license_challenge(self.cdm_session, pssh)
        license = self.session.post(
            "https://gue1-spclient.spotify.com/widevine-license/v1/audio/license",
            challenge,
        ).content
        self.cdm.parse_license(self.cdm_session, license)
        return next(
            i for i in self.cdm.get_keys(self.cdm_session) if i.type == "CONTENT"
        ).key.hex()

    def get_stream_url(self, file_id: str) -> str:
        return self.session.get(
            "https://gue1-spclient.spotify.com/storage-resolve/v2/files/audio/interactive/11/"
            + f"{file_id}?version=10000000&product=9&platform=39&alt=json",
        ).json()["cdnurl"][0]

    def get_artist(self, artist_list: list[dict]) -> str:
        if len(artist_list) == 1:
            return artist_list[0]["name"]
        return (
            ", ".join(i["name"] for i in artist_list[:-1])
            + f' & {artist_list[-1]["name"]}'
        )

    def get_lyrics_synced_timestamp_lrc(self, time: int) -> str:
        lrc_timestamp = datetime.datetime.fromtimestamp(time / 1000.0)
        return lrc_timestamp.strftime("%M:%S.%f")[:-4]

    def get_lyrics(self, track_id: str) -> tuple[str, str]:
        lyrics_response = self.session.get(
            f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}"
        )
        if lyrics_response.status_code == 404:
            return None, None
        lyrics_raw = lyrics_response.json()["lyrics"]
        lyrics_synced = ""
        lyrics_unsynced = ""
        for line in lyrics_raw["lines"]:
            if lyrics_raw["syncType"] == "LINE_SYNCED":
                lyrics_synced += f'[{self.get_lyrics_synced_timestamp_lrc(int(line["startTimeMs"]))}]{line["words"]}\n'
            lyrics_unsynced += f'{line["words"]}\n'
        return lyrics_unsynced[:-1], lyrics_synced

    @functools.lru_cache()
    def get_cover(self, url: str) -> bytes:
        return requests.get(url).content

    def get_iso_release_date(
        self, release_date_precision: str, release_date: str
    ) -> str:
        if release_date_precision == "year":
            datetime_template = "%Y"
        elif release_date_precision == "month":
            datetime_template = "%Y-%m"
        else:
            datetime_template = "%Y-%m-%d"
        return (
            datetime.datetime.strptime(release_date, datetime_template).isoformat()
            + "Z"
        )

    def get_cover_url(self, metadata: dict) -> str:
        return "https://i.scdn.co/image/" + next(
            i["file_id"]
            for i in metadata["album"]["cover_group"]["image"]
            if i["size"] == "LARGE"
        )

    def get_tags(self, metadata: dict, lyrics_unsynced: str) -> dict:
        album = self.get_album(self.gid_to_uri(metadata["album"]["gid"]))
        isrc = next((i for i in metadata["external_id"] if i["type"] == "isrc"), None)
        tags = {
            "album": metadata["album"]["name"],
            "album_artist": self.get_artist(metadata["album"]["artist"]),
            "artist": self.get_artist(metadata["artist"]),
            "comment": f'https://open.spotify.com/track/{metadata["canonical_uri"].split(":")[-1]}',
            "compilation": True if album["album_type"] == "compilation" else False,
            "copyright": next(
                (i["text"] for i in album["copyrights"] if i["type"] == "P"), None
            ),
            "disc": metadata["disc_number"],
            "disc_total": album["tracks"]["items"][-1]["disc_number"],
            "isrc": isrc.get("id") if isrc is not None else None,
            "label": metadata["album"].get("label"),
            "lyrics": lyrics_unsynced,
            "media_type": 1,
            "rating": 1 if "explicit" in metadata else 0,
            "title": metadata["name"],
            "track": metadata["number"],
            "track_total": max(
                i["track_number"]
                for i in album["tracks"]["items"]
                if i["disc_number"] == metadata["disc_number"]
            ),
            "release_date": self.get_iso_release_date(
                album["release_date_precision"], album["release_date"]
            ),
        }
        tags["release_year"] = tags["release_date"][:4]
        return tags

    def get_sanitized_string(self, dirty_string: str, is_folder: bool) -> str:
        dirty_string = re.sub(r'[\\/:*?"<>|;]', "_", dirty_string)
        if is_folder:
            dirty_string = dirty_string[: self.truncate]
            if dirty_string.endswith("."):
                dirty_string = dirty_string[:-1] + "_"
        else:
            if self.truncate is not None:
                dirty_string = dirty_string[: self.truncate - 4]
        return dirty_string.strip()

    def get_encrypted_location(self, track_id: str) -> Path:
        return self.temp_path / f"{track_id}_encrypted.m4a"

    def get_fixed_location(self, track_id: str) -> Path:
        return self.temp_path / f"{track_id}_fixed.m4a"

    def get_cover_location(self, final_location: Path) -> Path:
        return final_location.parent / "Cover.jpg"

    def get_lrc_location(self, final_location: Path) -> Path:
        return final_location.with_suffix(".lrc")

    def get_final_location(self, tags: dict) -> Path:
        final_location_folder = (
            self.template_folder_compilation.split("/")
            if tags["compilation"]
            else self.template_folder_album.split("/")
        )
        final_location_file = (
            self.template_file_multi_disc.split("/")
            if tags["disc_total"] > 1
            else self.template_file_single_disc.split("/")
        )
        final_location_folder = [
            self.get_sanitized_string(i.format(**tags), True)
            for i in final_location_folder
        ]
        final_location_file = [
            self.get_sanitized_string(i.format(**tags), True)
            for i in final_location_file[:-1]
        ] + [
            self.get_sanitized_string(final_location_file[-1].format(**tags), False)
            + ".m4a"
        ]
        return self.final_path.joinpath(*final_location_folder).joinpath(
            *final_location_file
        )

    def download_ytdlp(self, encrypted_location: Path, stream_url: str) -> None:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "outtmpl": str(encrypted_location),
                "allow_unplayable_formats": True,
                "fixup": "never",
                "allowed_extractors": ["generic"],
            }
        ) as ydl:
            ydl.download(stream_url)

    def download_aria2c(self, encrypted_location: Path, stream_url: str) -> None:
        encrypted_location.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                self.aria2c_location,
                "--no-conf",
                "--download-result=hide",
                "--console-log-level=error",
                "--summary-interval=0",
                "--file-allocation=none",
                stream_url,
                "--out",
                encrypted_location,
            ],
            check=True,
        )
        print("\r", end="")

    def fixup(
        self, decryption_key: str, encrypted_location: Path, fixed_location: Path
    ) -> None:
        subprocess.run(
            [
                self.ffmpeg_location,
                "-loglevel",
                "error",
                "-y",
                "-decryption_key",
                decryption_key,
                "-i",
                encrypted_location,
                "-movflags",
                "+faststart",
                "-c",
                "copy",
                fixed_location,
            ],
            check=True,
        )

    def apply_tags(self, fixed_location: Path, tags: dict, cover_url: str) -> None:
        mp4_tags = {
            v: [tags[k]]
            for k, v in MP4_TAGS_MAP.items()
            if k not in self.exclude_tags and tags.get(k) is not None
        }
        if not {"track", "track_total"} & set(self.exclude_tags):
            mp4_tags["trkn"] = [[0, 0]]
        if not {"disc", "disc_total"} & set(self.exclude_tags):
            mp4_tags["disk"] = [[0, 0]]
        if "compilation" not in self.exclude_tags:
            mp4_tags["cpil"] = tags["compilation"]
        if "cover" not in self.exclude_tags:
            mp4_tags["covr"] = [
                MP4Cover(self.get_cover(cover_url), imageformat=MP4Cover.FORMAT_JPEG)
            ]
        if "isrc" not in self.exclude_tags and tags.get("isrc") is not None:
            mp4_tags["----:com.apple.iTunes:ISRC"] = [
                MP4FreeForm(tags["isrc"].encode("utf-8"))
            ]
        if "label" not in self.exclude_tags and tags.get("label") is not None:
            mp4_tags["----:com.apple.iTunes:LABEL"] = [
                MP4FreeForm(tags["label"].encode("utf-8"))
            ]
        if "track" not in self.exclude_tags:
            mp4_tags["trkn"][0][0] = tags["track"]
        if "track_total" not in self.exclude_tags:
            mp4_tags["trkn"][0][1] = tags["track_total"]
        if "disc" not in self.exclude_tags:
            mp4_tags["disk"][0][0] = tags["disc"]
        if "disc_total" not in self.exclude_tags:
            mp4_tags["disk"][0][1] = tags["disc_total"]
        mp4 = MP4(fixed_location)
        mp4.clear()
        mp4.update(mp4_tags)
        mp4.save()

    def move_to_final_location(self, fixed_location: Path, final_location: Path):
        final_location.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(fixed_location, final_location)

    @functools.lru_cache()
    def save_cover(self, cover_location: Path, cover_url: str):
        with open(cover_location, "wb") as f:
            f.write(self.get_cover(cover_url))

    def save_lrc(self, lrc_location: Path, lyrics_unsynced: str):
        lrc_location.parent.mkdir(parents=True, exist_ok=True)
        with open(lrc_location, "w", encoding="utf8") as f:
            f.write(lyrics_unsynced)

    def cleanup_temp_path(self) -> None:
        shutil.rmtree(self.temp_path)
