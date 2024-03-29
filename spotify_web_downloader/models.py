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
