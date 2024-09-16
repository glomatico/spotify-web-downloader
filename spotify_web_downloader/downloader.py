from __future__ import annotations

import datetime
import functools
import re
import shutil
import subprocess
from pathlib import Path

import requests
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from pywidevine import Cdm, Device

from .constants import *
from .enums import RemuxMode
from .models import DownloadQueue, UrlInfo
from .spotify_api import SpotifyApi
from .utils import check_response


class Downloader:
    ILLEGAL_CHARACTERS_REGEX = r'[\\/:*?"<>|;]'
    URL_RE = r"(album|playlist|track)/(\w{22})"
    ILLEGAL_CHARACTERS_REPLACEMENT = "_"

    def __init__(
        self,
        spotify_api: SpotifyApi,
        output_path: Path = Path("./Spotify"),
        temp_path: Path = Path("./temp"),
        wvd_path: Path = Path("./device.wvd"),
        ffmpeg_path: str = "ffmpeg",
        mp4box_path: str = "MP4Box",
        mp4decrypt_path: str = "mp4decrypt",
        aria2c_path: str = "aria2c",
        nm3u8dlre_path: str = "N_m3u8DL-RE",
        remux_mode: RemuxMode = RemuxMode.FFMPEG,
        template_folder_album: str = "{album_artist}/{album}",
        template_folder_compilation: str = "Compilations/{album}",
        template_file_single_disc: str = "{track:02d} {title}",
        template_file_multi_disc: str = "{disc}-{track:02d} {title}",
        template_folder_no_album: str = "{artist}/Unknown Album",
        template_file_no_album: str = "{title}",
        template_file_playlist: str = "Playlists/{playlist_artist}/{playlist_title}",
        date_tag_template: str = "%Y-%m-%dT%H:%M:%SZ",
        exclude_tags: str = None,
        truncate: int = None,
        silence: bool = False,
    ):
        self.spotify_api = spotify_api
        self.output_path = output_path
        self.temp_path = temp_path
        self.wvd_path = wvd_path
        self.ffmpeg_path = ffmpeg_path
        self.mp4box_path = mp4box_path
        self.mp4decrypt_path = mp4decrypt_path
        self.aria2c_path = aria2c_path
        self.nm3u8dlre_path = nm3u8dlre_path
        self.remux_mode = remux_mode
        self.template_folder_album = template_folder_album
        self.template_folder_compilation = template_folder_compilation
        self.template_file_single_disc = template_file_single_disc
        self.template_file_multi_disc = template_file_multi_disc
        self.template_folder_no_album = template_folder_no_album
        self.template_file_no_album = template_file_no_album
        self.template_file_playlist = template_file_playlist
        self.date_tag_template = date_tag_template
        self.exclude_tags = exclude_tags
        self.truncate = truncate
        self.silence = silence
        self._set_binaries_full_path()
        self._set_exclude_tags_list()
        self._set_truncate()
        self._set_subprocess_additional_args()

    def _set_binaries_full_path(self):
        self.ffmpeg_path_full = shutil.which(self.ffmpeg_path)
        self.mp4box_path_full = shutil.which(self.mp4box_path)
        self.mp4decrypt_path_full = shutil.which(self.mp4decrypt_path)
        self.aria2c_path_full = shutil.which(self.aria2c_path)
        self.nm3u8dlre_path_full = shutil.which(self.nm3u8dlre_path)

    def _set_exclude_tags_list(self):
        self.exclude_tags_list = (
            [i.lower() for i in self.exclude_tags.split(",")]
            if self.exclude_tags is not None
            else []
        )

    def _set_truncate(self):
        if self.truncate is not None:
            self.truncate = None if self.truncate < 4 else self.truncate

    def _set_subprocess_additional_args(self):
        if self.silence:
            self.subprocess_additional_args = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
        else:
            self.subprocess_additional_args = {}

    def set_cdm(self) -> None:
        self.cdm = Cdm.from_device(Device.load(self.wvd_path))

    def get_url_info(self, url: str) -> UrlInfo:
        url_regex_result = re.search(self.URL_RE, url)
        if url_regex_result is None:
            raise Exception("Invalid URL")
        return UrlInfo(type=url_regex_result.group(1), id=url_regex_result.group(2))

    def get_download_queue(
        self,
        url_info: UrlInfo,
    ) -> DownloadQueue:
        download_queue = DownloadQueue(tracks_metadata=[])
        if url_info.type == "album":
            download_queue.tracks_metadata.extend(
                track_metadata
                for track_metadata in self.spotify_api.get_album(url_info.id)["tracks"][
                    "items"
                ]
                if track_metadata is not None
            )
        elif url_info.type == "playlist":
            playlist = self.spotify_api.get_playlist(url_info.id)
            download_queue.playlist_metadata = playlist.copy()
            download_queue.playlist_metadata.pop("tracks")
            download_queue.tracks_metadata.extend(
                track_metadata["track"]
                for track_metadata in playlist["tracks"]["items"]
                if track_metadata["track"] is not None
            )
        elif url_info.type == "track":
            download_queue.tracks_metadata.append(
                self.spotify_api.get_track(url_info.id)
            )
        return download_queue

    def get_playlist_tags(self, playlist_metadata: dict, playlist_track: int) -> dict:
        return {
            "playlist_artist": playlist_metadata["owner"]["display_name"],
            "playlist_title": playlist_metadata["name"],
            "playlist_track": playlist_track,
        }

    def get_playlist_file_path(
        self,
        tags: dict,
    ):
        template_file = self.template_file_playlist.split("/")
        return Path(
            self.output_path,
            *[
                self.get_sanitized_string(i.format(**tags), True)
                for i in template_file[0:-1]
            ],
            *[
                self.get_sanitized_string(template_file[-1].format(**tags), False)
                + ".m3u8"
            ],
        )

    def get_final_path(self, tags: dict, file_extension: str) -> Path:
        if tags.get("album"):
            template_folder = (
                self.template_folder_compilation.split("/")
                if tags.get("compilation")
                else self.template_folder_album.split("/")
            )
            template_file = (
                self.template_file_multi_disc.split("/")
                if tags["disc_total"] > 1
                else self.template_file_single_disc.split("/")
            )
        else:
            template_folder = self.template_folder_no_album.split("/")
            template_file = self.template_file_no_album.split("/")
        template_final = template_folder + template_file
        return Path(
            self.output_path,
            *[
                self.get_sanitized_string(i.format(**tags), True)
                for i in template_final[0:-1]
            ],
            (
                self.get_sanitized_string(template_final[-1].format(**tags), False)
                + file_extension
            ),
        )

    def update_playlist_file(
        self,
        playlist_file_path: Path,
        final_path: Path,
        playlist_track: int,
    ):
        playlist_file_path.parent.mkdir(parents=True, exist_ok=True)
        playlist_file_path_parent_parts_len = len(playlist_file_path.parent.parts)
        output_path_parts_len = len(self.output_path.parts)
        final_path_relative = Path(
            ("../" * (playlist_file_path_parent_parts_len - output_path_parts_len)),
            *final_path.parts[output_path_parts_len:],
        )
        playlist_file_lines = (
            playlist_file_path.open("r", encoding="utf8").readlines()
            if playlist_file_path.exists()
            else []
        )
        if len(playlist_file_lines) < playlist_track:
            playlist_file_lines.extend(
                "\n" for _ in range(playlist_track - len(playlist_file_lines))
            )
        playlist_file_lines[playlist_track - 1] = final_path_relative.as_posix() + "\n"
        with playlist_file_path.open("w", encoding="utf8") as playlist_file:
            playlist_file.writelines(playlist_file_lines)

    def get_sanitized_string(self, dirty_string: str, is_folder: bool) -> str:
        dirty_string = re.sub(
            self.ILLEGAL_CHARACTERS_REGEX,
            self.ILLEGAL_CHARACTERS_REPLACEMENT,
            dirty_string,
        )
        if is_folder:
            dirty_string = dirty_string[: self.truncate]
            if dirty_string.endswith("."):
                dirty_string = dirty_string[:-1] + self.ILLEGAL_CHARACTERS_REPLACEMENT
        else:
            if self.truncate is not None:
                dirty_string = dirty_string[: self.truncate - 4]
        return dirty_string.strip()

    def get_release_date_datetime_obj(self, metadata_gid: dict) -> datetime.datetime:
        metadata_gid_release_date = metadata_gid["album"]["date"]
        if metadata_gid_release_date.get("day"):
            datetime_obj = datetime.datetime(
                year=metadata_gid_release_date["year"],
                month=metadata_gid_release_date["month"],
                day=metadata_gid_release_date["day"],
            )
        elif metadata_gid_release_date.get("month"):
            datetime_obj = datetime.datetime(
                year=metadata_gid_release_date["year"],
                month=metadata_gid_release_date["month"],
                day=1,
            )
        else:
            datetime_obj = datetime.datetime(
                year=metadata_gid_release_date["year"],
                month=1,
                day=1,
            )
        return datetime_obj

    def get_release_date_tag(self, datetime_obj: datetime.datetime) -> str:
        return datetime_obj.strftime(self.date_tag_template)

    def get_artist(self, artist_list: list[dict]) -> str:
        if len(artist_list) == 1:
            return artist_list[0]["name"]
        return (
            ", ".join(i["name"] for i in artist_list[:-1])
            + f' & {artist_list[-1]["name"]}'
        )

    def get_cover_url(self, metadata_gid: dict, size: str) -> str | None:
        if not metadata_gid["album"].get("cover_group"):
            return None
        return "https://i.scdn.co/image/" + next(
            i["file_id"]
            for i in metadata_gid["album"]["cover_group"]["image"]
            if i["size"] == size
        )

    def get_encrypted_path(
        self,
        track_id: str,
        file_extension: str,
    ) -> Path:
        return self.temp_path / (f"{track_id}_encrypted" + file_extension)

    def get_decrypted_path(
        self,
        track_id: str,
        file_extension: str,
    ) -> Path:
        return self.temp_path / (f"{track_id}_decrypted" + file_extension)

    def get_remuxed_path(
        self,
        track_id: str,
        file_extension: str,
    ) -> Path:
        return self.temp_path / (f"{track_id}_remuxed" + file_extension)

    def decrypt_mp4decrypt(
        self,
        encrypted_path: Path,
        decrypted_path: Path,
        decryption_key: str,
    ):
        subprocess.run(
            [
                self.mp4decrypt_path_full,
                encrypted_path,
                "--key",
                f"1:{decryption_key}",
                decrypted_path,
            ],
            check=True,
            **self.subprocess_additional_args,
        )

    @staticmethod
    @functools.lru_cache()
    def get_response_bytes(url: str) -> bytes:
        response = requests.get(url)
        check_response(response)
        return response.content

    def apply_tags(self, fixed_location: Path, tags: dict, cover_url: str):
        to_apply_tags = [
            tag_name
            for tag_name in tags.keys()
            if tag_name not in self.exclude_tags_list
        ]
        mp4_tags = {}
        for tag_name in to_apply_tags:
            if tags.get(tag_name) is None:
                continue
            if tag_name in ("disc", "disc_total"):
                if mp4_tags.get("disk") is None:
                    mp4_tags["disk"] = [[0, 0]]
                if tag_name == "disc":
                    mp4_tags["disk"][0][0] = tags[tag_name]
                elif tag_name == "disc_total":
                    mp4_tags["disk"][0][1] = tags[tag_name]
            elif tag_name in ("track", "track_total"):
                if mp4_tags.get("trkn") is None:
                    mp4_tags["trkn"] = [[0, 0]]
                if tag_name == "track":
                    mp4_tags["trkn"][0][0] = tags[tag_name]
                elif tag_name == "track_total":
                    mp4_tags["trkn"][0][1] = tags[tag_name]
            elif tag_name == "compilation":
                mp4_tags["cpil"] = tags["compilation"]
            elif tag_name == "isrc":
                mp4_tags["----:com.apple.iTunes:ISRC"] = [
                    MP4FreeForm(tags["isrc"].encode("utf-8"))
                ]
            elif tag_name == "label":
                mp4_tags["----:com.apple.iTunes:LABEL"] = [
                    MP4FreeForm(tags["label"].encode("utf-8"))
                ]
            elif MP4_TAGS_MAP.get(tag_name) is not None:
                mp4_tags[MP4_TAGS_MAP[tag_name]] = [tags[tag_name]]
        if "cover" not in self.exclude_tags_list and cover_url is not None:
            mp4_tags["covr"] = [
                MP4Cover(
                    self.get_response_bytes(cover_url), imageformat=MP4Cover.FORMAT_JPEG
                )
            ]
        mp4 = MP4(fixed_location)
        mp4.clear()
        mp4.update(mp4_tags)
        mp4.save()

    def move_to_final_path(self, fixed_path: Path, final_path: Path):
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(fixed_path, final_path)

    @functools.lru_cache()
    def save_cover(self, cover_path: Path, cover_url: str):
        if cover_url is not None:
            cover_path.parent.mkdir(parents=True, exist_ok=True)
            cover_path.write_bytes(self.get_response_bytes(cover_url))

    def cleanup_temp_path(self):
        shutil.rmtree(self.temp_path)
