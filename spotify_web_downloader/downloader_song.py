import datetime
import functools
import subprocess
from pathlib import Path

from pywidevine import PSSH
from yt_dlp import YoutubeDL

from .downloader import Downloader
from .enums import DownloadModeSong
from .models import Lyrics


class DownloaderSong:
    def __init__(
        self,
        downloader: Downloader,
        template_folder_album: str = "{album_artist}/{album}",
        template_folder_compilation: str = "Compilations/{album}",
        template_file_single_disc: str = "{track:02d} {title}",
        template_file_multi_disc: str = "{disc}-{track:02d} {title}",
        download_mode: DownloadModeSong = DownloadModeSong.YTDLP,
        premium_quality: bool = False,
    ):
        self.downloader = downloader
        self.template_folder_album = template_folder_album
        self.template_folder_compilation = template_folder_compilation
        self.template_file_single_disc = template_file_single_disc
        self.template_file_multi_disc = template_file_multi_disc
        self.download_mode = download_mode
        self.premium_quality = premium_quality
        self._set_codec()

    def _set_codec(self):
        self.codec = "MP4_256" if self.premium_quality else "MP4_128"

    def get_final_path(self, tags: dict) -> Path:
        final_path_folder = (
            self.template_folder_compilation.split("/")
            if tags["compilation"]
            else self.template_folder_album.split("/")
        )
        final_path_file = (
            self.template_file_multi_disc.split("/")
            if tags["disc_total"] > 1
            else self.template_file_single_disc.split("/")
        )
        final_path_folder = [
            self.downloader.get_sanitized_string(i.format(**tags), True)
            for i in final_path_folder
        ]
        final_path_file = [
            self.downloader.get_sanitized_string(i.format(**tags), True)
            for i in final_path_file[:-1]
        ] + [
            self.downloader.get_sanitized_string(
                final_path_file[-1].format(**tags), False
            )
            + ".m4a"
        ]
        return self.downloader.output_path.joinpath(*final_path_folder).joinpath(
            *final_path_file
        )

    def get_decryption_key(self, pssh: str) -> str:
        pssh = PSSH(pssh)
        cdm_session = self.downloader.cdm.open()
        challenge = self.downloader.cdm.get_license_challenge(cdm_session, pssh)
        license = self.downloader.spotify_api.get_widevine_license_music(challenge)
        self.downloader.cdm.parse_license(cdm_session, license)
        decryption_key = next(
            i for i in self.downloader.cdm.get_keys(cdm_session) if i.type == "CONTENT"
        ).key.hex()
        self.downloader.cdm.close(cdm_session)
        return decryption_key

    def get_file_id(self, metadata_gid: dict) -> str:
        audio_files = metadata_gid.get("file")
        if audio_files is None:
            if metadata_gid.get("alternative") is not None:
                audio_files = metadata_gid["alternative"][0]["file"]
            else:
                return None
        return next(i["file_id"] for i in audio_files if i["format"] == self.codec)

    def get_tags(
        self,
        metadata_gid: dict,
        album_metadata: dict,
        track_credits: dict,
        lyrics_unsynced: str,
    ) -> dict:
        isrc = None
        if metadata_gid.get("external_id"):
            isrc = next(
                (i for i in metadata_gid["external_id"] if i["type"] == "isrc"), None
            )
        release_date_datetime_obj = self.downloader.get_release_date_datetime_obj(
            metadata_gid
        )
        producers = next(
            role
            for role in track_credits["roleCredits"]
            if role["roleTitle"] == "Producers"
        )["artists"]
        composers = next(
            role
            for role in track_credits["roleCredits"]
            if role["roleTitle"] == "Writers"
        )["artists"]
        tags = {
            "album": album_metadata["name"],
            "album_artist": self.downloader.get_artist(album_metadata["artists"]),
            "artist": self.downloader.get_artist(metadata_gid["artist"]),
            "compilation": (
                True if album_metadata["album_type"] == "compilation" else False
            ),
            "composer": self.downloader.get_artist(composers) if composers else None,
            "copyright": next(
                (i["text"] for i in album_metadata["copyrights"] if i["type"] == "P"),
                None,
            ),
            "disc": metadata_gid["disc_number"],
            "disc_total": album_metadata["tracks"]["items"][-1]["disc_number"],
            "isrc": isrc.get("id") if isrc is not None else None,
            "label": album_metadata.get("label"),
            "lyrics": lyrics_unsynced,
            "media_type": 1,
            "producer": self.downloader.get_artist(producers) if producers else None,
            "rating": 1 if metadata_gid.get("explicit") else 0,
            "release_date": self.downloader.get_release_date_tag(
                release_date_datetime_obj
            ),
            "release_year": str(release_date_datetime_obj.year),
            "title": metadata_gid["name"],
            "track": metadata_gid["number"],
            "track_total": max(
                i["track_number"]
                for i in album_metadata["tracks"]["items"]
                if i["disc_number"] == metadata_gid["disc_number"]
            ),
            "url": f"https://open.spotify.com/track/{self.downloader.spotify_api.gid_to_track_id(metadata_gid['gid'])}",
        }
        return tags

    def download(self, encrypted_path: Path, stream_url: str):
        if self.download_mode == DownloadModeSong.YTDLP:
            self.download_ytdlp(encrypted_path, stream_url)
        elif self.download_mode == DownloadModeSong.ARIA2C:
            self.download_aria2c(encrypted_path, stream_url)

    def download_ytdlp(self, encrypted_path: Path, stream_url: str) -> None:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "outtmpl": str(encrypted_path),
                "allow_unplayable_formats": True,
                "fixup": "never",
                "allowed_extractors": ["generic"],
                "noprogress": self.downloader.no_progress,
            }
        ) as ydl:
            ydl.download(stream_url)

    def download_aria2c(self, encrypted_path: Path, stream_url: str) -> None:
        if self.downloader.no_progress:
            subprocess_additional_args = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
        else:
            subprocess_additional_args = {}
        encrypted_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                self.downloader.aria2c_path_full,
                "--no-conf",
                "--download-result=hide",
                "--console-log-level=error",
                "--summary-interval=0",
                "--file-allocation=none",
                stream_url,
                "--out",
                encrypted_path,
            ],
            check=True,
            **subprocess_additional_args,
        )
        print("\r", end="")

    def fixup(
        self,
        decryption_key: str,
        encrypted_path: Path,
        fixed_path: Path,
    ) -> None:
        subprocess.run(
            [
                self.downloader.ffmpeg_path_full,
                "-loglevel",
                "error",
                "-y",
                "-decryption_key",
                decryption_key,
                "-i",
                encrypted_path,
                "-movflags",
                "+faststart",
                "-fflags",
                "+bitexact",
                "-c",
                "copy",
                fixed_path,
            ],
            check=True,
        )

    def get_lyrics_synced_timestamp_lrc(self, time: int) -> str:
        lrc_timestamp = datetime.datetime.fromtimestamp(
            time / 1000.0, tz=datetime.timezone.utc
        )
        return lrc_timestamp.strftime("%M:%S.%f")[:-4]

    def get_lyrics(self, track_id: str) -> Lyrics:
        lyrics = Lyrics()
        raw_lyrics = self.downloader.spotify_api.get_lyrics(track_id)
        if raw_lyrics is None:
            return lyrics
        lyrics.synced = ""
        lyrics.unsynced = ""
        for line in raw_lyrics["lyrics"]["lines"]:
            if raw_lyrics["lyrics"]["syncType"] == "LINE_SYNCED":
                lyrics.synced += f'[{self.get_lyrics_synced_timestamp_lrc(int(line["startTimeMs"]))}]{line["words"]}\n'
            lyrics.unsynced += f'{line["words"]}\n'
        lyrics.unsynced = lyrics.unsynced[:-1]
        return lyrics

    def get_cover_path(self, final_path: Path) -> Path:
        return final_path.parent / "Cover.jpg"

    def get_lrc_path(self, final_path: Path) -> Path:
        return final_path.with_suffix(".lrc")

    def save_lrc(self, lrc_path: Path, lyrics_synced: str):
        if lyrics_synced:
            lrc_path.parent.mkdir(parents=True, exist_ok=True)
            lrc_path.write_text(lyrics_synced, encoding="utf8")
