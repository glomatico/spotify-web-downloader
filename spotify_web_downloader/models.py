from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Lyrics:
    synced: str = None
    unsynced: str = None


@dataclass
class UrlInfo:
    type: str = None
    id: str = None


@dataclass
class DownloadQueueItem:
    metadata: dict = None


@dataclass
class VideoStreamInfo:
    base_url: str = None
    initialization_template_url: str = None
    segment_template_url: str = None
    end_time_millis: int = None
    segment_length: int = None
    profile_id_video: int = None
    profile_id_audio: int = None
    file_type_video: str = None
    file_type_audio: str = None
    pssh: str = None


@dataclass
class VideoM3U8:
    video: str = None
    audio: str = None
