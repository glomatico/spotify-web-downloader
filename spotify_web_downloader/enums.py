from enum import Enum


class DownloadModeSong(Enum):
    YTDLP = "ytdlp"
    ARIA2C = "aria2c"


class DownloadModeVideo(Enum):
    YTDLP = "ytdlp"
    NM3U8DLRE = "nm3u8dlre"
