from __future__ import annotations

import subprocess
from pathlib import Path

from pywidevine import PSSH
from yt_dlp import YoutubeDL

from .downloader import Downloader
from .enums import DownloadModeVideo, RemuxMode
from .models import VideoM3U8, VideoStreamInfo


class DownloaderMusicVideo:
    M3U8_HEADER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-TARGETDURATION:1"""

    def __init__(
        self,
        downloader: Downloader,
        template_folder: str = "{artist}/Unknown Album",
        template_file: str = "{title}",
        download_mode: DownloadModeVideo = DownloadModeVideo.YTDLP,
    ):
        self.downloader = downloader
        self.template_folder = template_folder
        self.template_file = template_file
        self.download_mode = download_mode

    def get_music_video_id_from_song_id(
        self,
        track_id: str,
        artist_id: str,
    ) -> dict | None:
        now_playing_view = self.downloader.spotify_api.get_now_playing_view(
            track_id, artist_id
        )
        related_music_videos = now_playing_view["data"]["trackUnion"]["relatedVideos"][
            "items"
        ]
        if not related_music_videos:
            return
        return related_music_videos[0]["trackOfVideo"]["data"]["uri"].split(":")[-1]

    def get_final_path(self, tags: dict) -> Path:
        final_path_folder = self.template_folder.split("/")
        final_path_file = self.template_file.split("/")
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
            + ".mp4"
        ]
        return self.downloader.output_path.joinpath(*final_path_folder).joinpath(
            *final_path_file
        )

    def get_manifest(self, metadata_gid: dict) -> dict:
        return self.downloader.spotify_api.get_video_manifest(
            metadata_gid["original_video"][0]["gid"]
        )

    def get_video_stream_info(self, manifest: dict) -> VideoStreamInfo:
        video_formats = list(
            format
            for format in manifest["contents"][0]["profiles"]
            if format.get("video_bitrate") and format["file_type"] == "mp4"
        )
        audio_formats = list(
            format
            for format in manifest["contents"][0]["profiles"]
            if format.get("audio_bitrate") and format["file_type"] == "mp4"
        )
        best_video_format = max(video_formats, key=lambda x: x["video_bitrate"])
        best_audio_format = max(audio_formats, key=lambda x: x["audio_bitrate"])
        base_url = manifest["base_urls"][0]
        initialization_template_url = manifest["initialization_template"]
        segment_template_url = manifest["segment_template"]
        end_time_millis = manifest["end_time_millis"]
        segment_length = manifest["contents"][0]["segment_length"]
        profile_id_video = best_video_format["id"]
        profile_id_audio = best_audio_format["id"]
        file_type_video = best_video_format["file_type"]
        file_type_audio = best_audio_format["file_type"]
        pssh = next(
            encryption_info
            for encryption_info in manifest["contents"][0]["encryption_infos"]
            if encryption_info["key_system"] == "widevine"
        )["encryption_data"]
        return VideoStreamInfo(
            base_url,
            initialization_template_url,
            segment_template_url,
            end_time_millis,
            segment_length,
            profile_id_video,
            profile_id_audio,
            file_type_video,
            file_type_audio,
            pssh,
        )

    def get_decryption_key(self, pssh: str) -> str:
        try:
            pssh = PSSH(pssh)
            cdm_session = self.downloader.cdm.open()
            challenge = self.downloader.cdm.get_license_challenge(cdm_session, pssh)
            license = self.downloader.spotify_api.get_widevine_license_video(challenge)
            self.downloader.cdm.parse_license(cdm_session, license)
            decryption_key = next(
                i
                for i in self.downloader.cdm.get_keys(cdm_session)
                if i.type == "CONTENT"
            ).key.hex()
        finally:
            self.downloader.cdm.close(cdm_session)
        return decryption_key

    def get_m3u8_path(self, track_id: str, type: str) -> Path:
        return self.downloader.temp_path / f"{track_id}_{type}.m3u8"

    def get_cover_path(self, final_path: Path) -> Path:
        return final_path.with_suffix(".jpg")

    def get_m3u8_str(self, segments: list) -> str:
        return (
            self.M3U8_HEADER
            + "\n"
            + "\n".join(f"#EXTINF:1,\n{i}" for i in segments)
            + "\n"
            + "#EXT-X-ENDLIST"
        )

    def get_m3u8(
        self,
        base_url: str,
        initialization_template_url: str,
        segment_template_url: str,
        end_time_millis: int,
        segment_length: int,
        profile_id_video: int,
        profile_id_audio: int,
        file_type_video: str,
        file_type_audio: str,
    ) -> VideoM3U8:
        segments_video, segments_audio = self.get_segment_urls(
            base_url,
            initialization_template_url,
            segment_template_url,
            end_time_millis,
            segment_length,
            profile_id_video,
            file_type_video,
        ), self.get_segment_urls(
            base_url,
            initialization_template_url,
            segment_template_url,
            end_time_millis,
            segment_length,
            profile_id_audio,
            file_type_audio,
        )
        m3u8_video = self.get_m3u8_str(segments_video)
        m3u8_audio = self.get_m3u8_str(segments_audio)
        return VideoM3U8(m3u8_video, m3u8_audio)

    def get_segment_urls(
        self,
        base_url: str,
        initialization_template_url: str,
        segment_template_url: str,
        end_time_millis: int,
        segment_length: int,
        profile_id: int,
        file_type: str,
    ) -> list[str]:
        initialization_template_url_formated = initialization_template_url.replace(
            "{{profile_id}}", str(profile_id)
        ).replace("{{file_type}}", file_type)
        segments = []
        first_segment = base_url + initialization_template_url_formated
        segments.append(first_segment)
        for i in range(0, int(end_time_millis / 1000) + 1, segment_length):
            segment_template_url_formated = (
                segment_template_url.replace("{{profile_id}}", str(profile_id))
                .replace("{{segment_timestamp}}", str(i))
                .replace("{{file_type}}", file_type)
            )
            segments.append(base_url + segment_template_url_formated)
        return segments

    def save_m3u8(self, m3u8_str: str, m3u8_path: Path) -> None:
        m3u8_path.parent.mkdir(parents=True, exist_ok=True)
        m3u8_path.write_text(m3u8_str)

    def get_tags(
        self,
        metadata_gid: dict,
        album_metadata: dict,
        track_credits: dict,
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
            "artist": self.downloader.get_artist(metadata_gid["artist"]),
            "composer": self.downloader.get_artist(composers) if composers else None,
            "copyright": next(
                (i["text"] for i in album_metadata["copyrights"] if i["type"] == "P"),
                None,
            ),
            "isrc": isrc.get("id") if isrc is not None else None,
            "label": metadata_gid["album"].get("label"),
            "media_type": 6,
            "producer": self.downloader.get_artist(producers) if producers else None,
            "rating": 1 if metadata_gid.get("explicit") else 0,
            "title": album_metadata["name"],
            "release_date": self.downloader.get_release_date_tag(
                release_date_datetime_obj
            ),
            "url": f"https://open.spotify.com/track/{self.downloader.spotify_api.gid_to_track_id(metadata_gid['gid'])}",
        }
        tags["release_year"] = str(release_date_datetime_obj.year)
        return tags

    def download(self, m3u8_path: Path, encrypted_path: str):
        if self.download_mode == DownloadModeVideo.YTDLP:
            self.download_ytdlp(m3u8_path, encrypted_path)
        elif self.download_mode == DownloadModeVideo.NM3U8DLRE:
            self.download_nm3u8dlre(m3u8_path, encrypted_path)

    def download_ytdlp(self, m3u8_path: Path, encrypted_path: Path) -> None:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "outtmpl": str(encrypted_path),
                "allow_unplayable_formats": True,
                "fixup": "never",
                "allowed_extractors": ["generic"],
                "noprogress": self.downloader.silence,
                "enable_file_urls": True,
            }
        ) as ydl:
            ydl.download(m3u8_path.resolve().as_uri())

    def download_nm3u8dlre(self, m3u8_path: Path, encrypted_path: Path) -> None:
        encrypted_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                self.downloader.nm3u8dlre_path_full,
                m3u8_path,
                "--binary-merge",
                "--no-log",
                "--log-level",
                "off",
                "--ffmpeg-binary-path",
                self.downloader.ffmpeg_path_full,
                "--save-name",
                encrypted_path.stem,
                "--save-dir",
                encrypted_path.parent,
                "--tmp-dir",
                encrypted_path.parent,
            ],
            check=True,
            **self.downloader.subprocess_additional_args,
        )

    def remux(
        self,
        decryption_key: str,
        encrypted_path_video: Path,
        encrypted_path_audio: Path,
        decrypted_path_video: Path,
        decrypted_path_audio: Path,
        remuxed_path: Path,
    ):
        if self.downloader.remux_mode == RemuxMode.FFMPEG:
            self.remux_ffmpeg(
                decryption_key,
                encrypted_path_video,
                encrypted_path_audio,
                remuxed_path,
            )
        elif self.downloader.remux_mode == RemuxMode.MP4BOX:
            self.downloader.decrypt_mp4decrypt(
                encrypted_path_video,
                decrypted_path_video,
                decryption_key,
            )
            self.downloader.decrypt_mp4decrypt(
                encrypted_path_audio,
                decrypted_path_audio,
                decryption_key,
            )
            self.remux_mp4box(
                decrypted_path_video,
                decrypted_path_audio,
                remuxed_path,
            )

    def remux_ffmpeg(
        self,
        decryption_key: str,
        encrypted_path_video: Path,
        encrypted_path_audio: Path,
        remuxed_path: Path,
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
                encrypted_path_video,
                "-decryption_key",
                decryption_key,
                "-i",
                encrypted_path_audio,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                remuxed_path,
            ],
            check=True,
            **self.downloader.subprocess_additional_args,
        )

    def remux_mp4box(
        self,
        decrypted_path_video: Path,
        decrypted_path_audio: Path,
        remuxed_path: Path,
    ):
        subprocess.run(
            [
                self.downloader.mp4box_path_full,
                "-quiet",
                "-add",
                decrypted_path_video,
                "-add",
                decrypted_path_audio,
                "-itags",
                "artist=placeholder",
                "-keep-utc",
                "-new",
                remuxed_path,
            ],
            check=True,
            **self.downloader.subprocess_additional_args,
        )
