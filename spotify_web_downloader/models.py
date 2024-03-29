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
    iniatialization_url_template: str = None
    segment_url_template: str = None
    end_time_millis: int = None
    segment_length: int = None
    profile_id_video: int = None
    profile_id_audio: int = None
    file_type_video: str = None
    file_type_audio: str = None
