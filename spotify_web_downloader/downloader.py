from __future__ import annotations

import datetime
import functools
import re
import shutil
from pathlib import Path

import requests
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from pywidevine import Cdm, Device

from .constants import *
from .hardcoded_wvd import HARDCODED_WVD
from .models import DownloadQueueItem, UrlInfo
from .spotify_api import SpotifyApi


class Downloader:
    ILLEGAL_CHARACTERS_REGEX = r'[\\/:*?"<>|;]'

    def __init__(
        self,
        spotify_api: SpotifyApi,
        output_path: Path = Path("./Spotify"),
        temp_path: Path = Path("./temp"),
        wvd_path: Path = None,
        ffmpeg_path: str = "ffmpeg",
        aria2c_path: str = "aria2c",
        nm3u8dlre_path: str = "N_m3u8DL-RE",
        date_tag_template: str = "%Y-%m-%dT%H:%M:%SZ",
        exclude_tags: str = None,
        truncate: int = 40,
        no_progress: bool = False,
    ):
        self.spotify_api = spotify_api
        self.output_path = output_path
        self.temp_path = temp_path
        self.wvd_path = wvd_path
        self.ffmpeg_path = ffmpeg_path
        self.aria2c_path = aria2c_path
        self.nm3u8dlre_path = nm3u8dlre_path
        self.date_tag_template = date_tag_template
        self.exclude_tags = exclude_tags
        self.truncate = truncate
        self.no_progress = no_progress
        self._set_binaries_full_path()
        self._set_exclude_tags_list()
        self._set_truncate()

    def _set_binaries_full_path(self):
        self.ffmpeg_path_full = shutil.which(self.ffmpeg_path)
        self.aria2c_path_full = shutil.which(self.aria2c_path)
        self.nm3u8dlre_path_full = shutil.which(self.nm3u8dlre_path)

    def _set_exclude_tags_list(self):
        self.exclude_tags_list = (
            [i.lower() for i in self.exclude_tags.split(",")]
            if self.exclude_tags is not None
            else []
        )

    def _set_truncate(self):
        self.truncate = None if self.truncate < 4 else self.truncate

    def set_cdm(self) -> None:
        if self.wvd_path:
            self.cdm = Cdm.from_device(Device.load(self.wvd_path))
        else:
            self.cdm = Cdm.from_device(Device.loads(HARDCODED_WVD))

    def get_url_info(self, url: str) -> UrlInfo:
        url_regex_result = re.search(r"(album|playlist|track)/(\w{22})", url)
        if url_regex_result is None:
            raise Exception("Invalid URL")
        return UrlInfo(type=url_regex_result.group(1), id=url_regex_result.group(2))

    def get_download_queue(self, url_info: UrlInfo) -> list[DownloadQueueItem]:
        download_queue = []
        if url_info.type == "album":
            download_queue.extend(
                [
                    DownloadQueueItem(metadata=track_metadata)
                    for track_metadata in self.spotify_api.get_album(url_info.id)[
                        "tracks"
                    ]["items"]
                ]
            )
        elif url_info.type == "playlist":
            download_queue.extend(
                [
                    DownloadQueueItem(metadata=track_metadata["track"])
                    for track_metadata in self.spotify_api.get_playlist(url_info.id)[
                        "tracks"
                    ]["items"]
                ]
            )
        elif url_info.type == "track":
            download_queue.append(
                DownloadQueueItem(metadata=self.spotify_api.get_track(url_info.id))
            )
        return download_queue

    def get_sanitized_string(self, dirty_string: str, is_folder: bool) -> str:
        dirty_string = re.sub(self.ILLEGAL_CHARACTERS_REGEX, "_", dirty_string)
        if is_folder:
            dirty_string = dirty_string[: self.truncate]
            if dirty_string.endswith("."):
                dirty_string = dirty_string[:-1] + "_"
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

    def get_cover_url(self, metadata_gid: dict, size: str) -> str:
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

    def get_fixed_path(
        self,
        track_id: str,
        file_extension: str,
    ) -> Path:
        return self.temp_path / (f"{track_id}_fixed" + file_extension)

    @staticmethod
    @functools.lru_cache()
    def get_image_bytes(url: str) -> bytes:
        return requests.get(url).content

    def apply_tags(self, fixed_location: Path, tags: dict, cover_url: str):
        mp4_tags = {
            v: [tags[k]]
            for k, v in MP4_TAGS_MAP.items()
            if k not in self.exclude_tags_list and tags.get(k) is not None
        }
        if not {"track", "track_total"} & set(self.exclude_tags_list) and tags.get(
            "track"
        ):
            mp4_tags["trkn"] = [[0, 0]]
        if not {"disc", "disc_total"} & set(self.exclude_tags_list) and tags.get(
            "disc"
        ):
            mp4_tags["disk"] = [[0, 0]]
        if (
            "compilation" not in self.exclude_tags_list
            and tags.get("compilation") is not None
        ):
            mp4_tags["cpil"] = tags["compilation"]
        if "cover" not in self.exclude_tags_list:
            mp4_tags["covr"] = [
                MP4Cover(
                    self.get_image_bytes(cover_url), imageformat=MP4Cover.FORMAT_JPEG
                )
            ]
        if "isrc" not in self.exclude_tags_list and tags.get("isrc") is not None:
            mp4_tags["----:com.apple.iTunes:ISRC"] = [
                MP4FreeForm(tags["isrc"].encode("utf-8"))
            ]
        if "label" not in self.exclude_tags_list and tags.get("label") is not None:
            mp4_tags["----:com.apple.iTunes:LABEL"] = [
                MP4FreeForm(tags["label"].encode("utf-8"))
            ]
        if "track" not in self.exclude_tags_list and tags.get("track") is not None:
            mp4_tags["trkn"][0][0] = tags["track"]
        if (
            "track_total" not in self.exclude_tags_list
            and tags.get("track_total") is not None
        ):
            mp4_tags["trkn"][0][1] = tags["track_total"]
        if "disc" not in self.exclude_tags_list and tags.get("disc") is not None:
            mp4_tags["disk"][0][0] = tags["disc"]
        if (
            "disc_total" not in self.exclude_tags_list
            and tags.get("disc_total") is not None
        ):
            mp4_tags["disk"][0][1] = tags["disc_total"]
        mp4 = MP4(fixed_location)
        mp4.clear()
        mp4.update(mp4_tags)
        mp4.save()

    def move_to_final_path(self, fixed_path: Path, final_path: Path):
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(fixed_path, final_path)

    @functools.lru_cache()
    def save_cover(self, cover_path: Path, cover_url: str):
        cover_path.write_bytes(self.get_image_bytes(cover_url))

    def cleanup_temp_path(self):
        shutil.rmtree(self.temp_path)
