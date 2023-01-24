from pathlib import Path
import re
import base64
import datetime
import subprocess
import shutil
import argparse
import traceback
from pathlib import Path
import functools
from pywidevine.L3.cdm.cdm import Cdm
from pywidevine.L3.cdm import deviceconfig
import requests
from librespot.metadata import TrackId
from librespot.metadata import AlbumId
from mutagen.mp4 import MP4, MP4Cover
from yt_dlp import YoutubeDL


class SpotifyAacDownloader:
    def __init__(self, cookies_location, premium_quality, temp_path, final_path, skip_cleanup, no_lrc):
        self.cdm = Cdm()
        self.temp_path = Path(temp_path)
        self.final_path = Path(final_path)
        self.skip_cleanup = skip_cleanup
        self.no_lrc = no_lrc
        if premium_quality:
            self.audio_quality = 'MP4_256'
        else:
            self.audio_quality = 'MP4_128'
        cookies = {}
        with open(Path(cookies_location), 'r') as f:
            for l in f:
                if not re.match(r"^#", l) and not re.match(r"^\n", l):
                    line_fields = l.strip().replace('&quot;', '"').split('\t')
                    cookies[line_fields[5]] = line_fields[6]
        self.session = requests.Session()
        self.session.headers.update({
            'app-platform': 'WebPlayer',
            'accept': 'application/json',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6,zh;q=0.5,ru;q=0.4,es;q=0.3,ja;q=0.2',
            'content-type': 'application/json',
            'origin': 'https://open.spotify.com',
            'referer': 'https://open.spotify.com/',
            'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        })
        self.session.cookies.update(cookies)
        web_page = self.session.get('https://open.spotify.com/').text
        token = re.search(r'accessToken":"(.*?)"', web_page).group(1)
        self.session.headers.update({
            'authorization': f'Bearer {token}'
        })


    def get_download_queue(self, url):
        spotify_id = url.split('/')[-1].split('?')[0]
        download_queue = []
        if 'track' in url:
            download_queue.append(
                self.get_metadata(TrackId.from_base62(spotify_id).get_gid().hex())
            )
        elif 'album' in url:
            for track in self.get_album(spotify_id)['tracks']['items']:
                download_queue.append(
                    self.get_metadata(TrackId.from_uri(track['uri']).get_gid().hex())
                )
        elif 'playlist' in url:
            for track in self.get_playlist(spotify_id)['tracks']['items']:
                download_queue.append(
                    self.get_metadata(TrackId.from_uri(track['track']['uri']).get_gid().hex())
                )
        if not download_queue:
            raise Exception('Not a valid Spotify URL')
        return download_queue
    

    @functools.lru_cache()
    def get_album(self, album_id):
        album = self.session.get(f'https://api.spotify.com/v1/albums/{album_id}').json()
        album_next_url = album['tracks']['next']
        while True:
            if album_next_url is None:
                break
            album_next = self.session.get(album_next_url).json()
            album['tracks']['items'].extend(album_next['items'])
            album_next_url = album_next['next']
        return album
    

    def get_playlist(self, playlist_id):
        playlist = self.session.get(f'https://api.spotify.com/v1/playlists/{playlist_id}').json()
        playlist_next_url = playlist['tracks']['next']
        while True:
            if playlist_next_url is None:
                break
            playlist_next = self.session.get(playlist_next_url).json()
            playlist['tracks']['items'].extend(playlist_next['items'])
            playlist_next_url = playlist_next['next']
        return playlist
    

    def get_metadata(self, gid):
        return self.session.get(f'https://spclient.wg.spotify.com/metadata/4/track/{gid}?market=from_token').json()
    

    def get_track_id(self, track):
        return track['canonical_uri'].split(':')[-1]


    def get_file_id(self, track):
        return next(i["file_id"] for i in track["file"] if i["format"] == self.audio_quality)
    

    def get_pssh(self, file_id):
        return self.session.get(f'https://seektables.scdn.co/seektable/{file_id}.json').json()['pssh']
    

    def check_pssh(self, pssh_b64):
        WV_SYSTEM_ID = [237, 239, 139, 169, 121, 214, 74, 206, 163, 200, 39, 220, 213, 29, 33, 237]
        pssh = base64.b64decode(pssh_b64)
        if not pssh[12:28] == bytes(WV_SYSTEM_ID):
            new_pssh = bytearray([0, 0, 0])
            new_pssh.append(32 + len(pssh))
            new_pssh[4:] = bytearray(b'pssh')
            new_pssh[8:] = [0, 0, 0, 0]
            new_pssh[13:] = WV_SYSTEM_ID
            new_pssh[29:] = [0, 0, 0, 0]
            new_pssh[31] = len(pssh)
            new_pssh[32:] = pssh
            return base64.b64encode(new_pssh)
        else:
            return pssh_b64
    

    def get_decryption_keys(self, pssh):
        session = self.cdm.open_session(
            self.check_pssh(pssh),
            deviceconfig.DeviceConfig(deviceconfig.device_android_generic)
        )
        challenge = self.cdm.get_license_request(session)
        license_b64 = base64.b64encode(
            self.session.post(
                'https://gue1-spclient.spotify.com/widevine-license/v1/audio/license', 
                challenge
            ).content
        )
        self.cdm.provide_license(session, license_b64)
        decryption_keys = []
        for key in self.cdm.get_keys(session):
            if key.type == 'CONTENT':
                decryption_keys.append(f'{key.kid.hex()}:{key.key.hex()}')
        return decryption_keys[0]
    
    
    def get_stream_url(self, file_id):
        return self.session.get(
            f'https://gue1-spclient.spotify.com/storage-resolve/v2/files/audio/interactive/11/{file_id}?version=10000000&product=9&platform=39&alt=json'
        ).json()['cdnurl'][0]
    

    def get_artist(self, artist_list):
        if len(artist_list) == 1:
            return artist_list[0]['name']
        artist = ', '.join(i['name'] for i in artist_list[:-1])
        artist += f' & {artist_list[-1]["name"]}'
        return artist
    

    def get_synced_lyrics_formated_time(self, time):
        formated_time = datetime.datetime.fromtimestamp(time / 1000.0)
        return formated_time.strftime('%M:%S.%f')[:-4]

    
    def get_lyrics(self, track_id):
        try:
            raw_lyrics = self.session.get(f'https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}').json()['lyrics']
        except:
            return None, None
        synced_lyrics = ''
        unsynced_lyrics = ''
        for line in raw_lyrics['lines']:
            if raw_lyrics['syncType'] == 'LINE_SYNCED':
                synced_lyrics += f'[{self.get_synced_lyrics_formated_time(int(line["startTimeMs"]))}]{line["words"]}\n'
            unsynced_lyrics += f'{line["words"]}\n'
        return unsynced_lyrics[:-1], synced_lyrics
    

    @functools.lru_cache()
    def get_cover(self, url):
        return requests.get(url).content
    

    def get_tags(self, track, unsynced_lyrics):
        album = self.get_album(AlbumId.from_hex(track['album']['gid']).to_spotify_uri().split(':')[-1])
        copyright = next(i['text'] for i in album['copyrights'] if i['type'] == 'P')
        if album['release_date_precision'] == 'year':
            release_date = album['release_date'] + '-01-01'
        else:
            release_date = album['release_date']
        total_tracks = [i['track_number'] for i in album['tracks']['items'] if i['disc_number'] == track['disc_number']][-1]
        total_discs = album['tracks']['items'][-1]['disc_number']
        tags = {
            '\xa9nam': [track['name']],
            '\xa9ART': [self.get_artist(track['artist'])],
            'aART': [self.get_artist(track['album']['artist'])],
            '\xa9alb': [track['album']['name']],
            'trkn': [(track['number'], total_tracks)],
            'disk': [(track['disc_number'], total_discs)],
            '\xa9day': [f'{release_date}T00:00:00Z'],
            'covr': [
                MP4Cover(
                    self.get_cover('https://i.scdn.co/image/' + next(i['file_id'] for i in track['album']['cover_group']['image'] if i['size'] == 'LARGE')),
                    imageformat = MP4Cover.FORMAT_JPEG
                )
            ],
            '\xa9cmt': [f'https://open.spotify.com/track/{track["canonical_uri"].split(":")[-1]}'],
            'cprt': [copyright],
            'rtng': [1] if 'explicit' in track else [0],
        }
        if unsynced_lyrics is not None:
            tags['\xa9lyr'] = [unsynced_lyrics]
        return tags
    

    def get_sanizated_string(self, dirty_string, is_folder):
        for character in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ';']:
            dirty_string = dirty_string.replace(character, '_')
        if is_folder:
            dirty_string = dirty_string[:40]
            if dirty_string[-1:] == '.':
                dirty_string = dirty_string[:-1] + '_'
        else:
            dirty_string = dirty_string[:36]
        return dirty_string.strip()
    

    def get_encrypted_location(self, track_id):
        return self.temp_path / f'{track_id}_encrypted.m4a'

    
    def get_decrypted_location(self, track_id):
        return self.temp_path / f'{track_id}_decrypted.m4a'
    

    def get_fixed_location(self, track_id):
        return self.temp_path / f'{track_id}_fixed.m4a'
    

    def get_final_location(self, tags):
        if tags['disk'][0][1] > 1:
            file_name = self.get_sanizated_string(f'{tags["disk"][0][0]}-{tags["trkn"][0][0]:02d} {tags["©nam"][0]}', False) + '.m4a'
        else:
            file_name = self.get_sanizated_string(f'{tags["trkn"][0][0]:02d} {tags["©nam"][0]}', False) + '.m4a'
        return self.final_path / self.get_sanizated_string(tags['aART'][0], True) / self.get_sanizated_string(tags['\xa9alb'][0], True) / file_name
        
    
    def download(self, encrypted_location, stream_url):
        with YoutubeDL({
            'quiet': True,
            'no_warnings': True,
            'outtmpl': str(encrypted_location),
            'allow_unplayable_formats': True,
            'fixup': 'never',
            'overwrites': True,
        }) as ydl:
            ydl.download(stream_url)
    

    def decrypt(self, keys, encrypted_location, decrypted_location):
        subprocess.run(
            [
                'mp4decrypt',
                encrypted_location,
                '--key',
                keys,
                decrypted_location
            ],
            check = True
        )
    

    def fixup(self, decrypted_location, fixed_location):
        subprocess.run(
            [
                'MP4Box',
                '-add',
                decrypted_location,
                '-itags',
                'album=placeholder',
                '-new',
                '-quiet',
                fixed_location
            ],
            check = True
        )
    

    def make_final(self, fixed_location, final_location, tags):
        final_location.parent.mkdir(parents = True, exist_ok = True)
        shutil.copy(fixed_location, final_location)
        file = MP4(final_location).tags
        for key, value in tags.items():
            file[key] = value
        file.save(final_location)


    def make_lrc(self, final_location, synced_lyrics):
        if synced_lyrics and not self.no_lrc:
            with open(final_location.with_suffix('.lrc'), 'w', encoding = 'utf8') as f:
                f.write(synced_lyrics)
    

    def cleanup(self):
        if self.temp_path.exists() and not self.skip_cleanup:
            shutil.rmtree(self.temp_path)


if __name__ == '__main__':
    if not shutil.which('mp4decrypt'):
        raise Exception('mp4decrypt is not on PATH')
    if not shutil.which('MP4Box'):
        raise Exception('MP4Box is not on PATH')
    parser = argparse.ArgumentParser(
        description = 'A Python script to download Spotify AAC songs/albums/playlists.',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'url',
        help='Spotify song/album/playlist URL(s)',
        nargs='*',
        metavar = '<url>'
    )
    parser.add_argument(
        '-u',
        '--urls-txt',
        help = 'Read URLs from a text file.',
        nargs = '?'
    )
    parser.add_argument(
        '-f',
        '--final-path',
        default = 'Spotify',
        help = 'Final Path.'
    )
    parser.add_argument(
        '-t',
        '--temp-path',
        default = 'temp',
        help = 'Temp Path.'
    )
    parser.add_argument(
        '-c',
        '--cookies-location',
        default = 'cookies.txt',
        help = 'Cookies location.'
    )
    parser.add_argument(
        '-n',
        '--no-lrc',
        action = 'store_true',
        help = "Don't create .lrc file."
    )
    parser.add_argument(
        '-p',
        '--premium-quality',
        action = 'store_true',
        help = 'Download AAC 256kbps instead of AAC 128kbps.'
    )
    parser.add_argument(
        '-s',
        '--skip-cleanup',
        action = 'store_true',
        help = 'Skip cleanup.'
    )
    parser.add_argument(
        '-e',
        '--print-exceptions',
        action = 'store_true',
        help = 'Print execeptions.'
    )
    args = parser.parse_args()
    if not args.url and not args.urls_txt:
        parser.error('you must specify an url or a text file using -u/--urls-txt.')
    if args.urls_txt:
        with open(args.urls_txt, 'r', encoding = 'utf8') as f:
            args.url = f.read().splitlines()
    dl = SpotifyAacDownloader(
        args.cookies_location,
        args.premium_quality,
        args.temp_path,
        args.final_path,
        args.skip_cleanup,
        args.no_lrc
    )
    download_queue = []
    error_count = 0
    for i, url in enumerate(args.url):
        try:
            download_queue.append(dl.get_download_queue(url.strip()))
        except KeyboardInterrupt:
            exit(1)
        except:
            error_count += 1
            print(f'* Failed to check URL {i + 1}.')
            if args.print_exceptions:
                traceback.print_exc()
    for i, url in enumerate(download_queue):
        for j, track in enumerate(url):
            print(f'Downloading "{track["name"]}" (track {j + 1} from URL {i + 1})...')
            try:
                file_id = dl.get_file_id(track)
                pssh = dl.get_pssh(file_id)
                decryption_keys = dl.get_decryption_keys(pssh)
                stream_url = dl.get_stream_url(file_id)
                track_id = dl.get_track_id(track)
                encrypted_location = dl.get_encrypted_location(track_id)
                dl.download(encrypted_location, stream_url)
                decrypted_location = dl.get_decrypted_location(track_id)
                dl.decrypt(decryption_keys, encrypted_location, decrypted_location)
                fixed_location = dl.get_fixed_location(track_id)
                dl.fixup(decrypted_location, fixed_location)
                unsynced_lyrics, synced_lyrics = dl.get_lyrics(track_id)
                tags = dl.get_tags(track, unsynced_lyrics)
                final_location = dl.get_final_location(tags)
                dl.make_final(fixed_location, final_location, tags)
                dl.make_lrc(final_location, synced_lyrics)
            except KeyboardInterrupt:
                exit(1)
            except:
                error_count += 1
                print(f'* Failed to download "{track["name"]}" (track {j + 1} from URL {i + 1}).')
                if args.print_exceptions:
                    traceback.print_exc()
            dl.cleanup()
    print(f'Done ({error_count} error(s)).')
