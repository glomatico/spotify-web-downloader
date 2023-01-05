from pathlib import Path
import re
import base64
from pywidevine.L3.cdm.cdm import Cdm
from pywidevine.L3.cdm import deviceconfig
import requests
from librespot.metadata import TrackId
from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path
from yt_dlp import YoutubeDL
import subprocess
import shutil
import argparse
import traceback


class SpotifyAacDownloader:
    def __init__(self, cookies_location, premium_quality, temp_path, final_path, skip_cleanup):
        self.cdm = Cdm()
        self.temp_path = Path(temp_path)
        self.final_path = Path(final_path)
        self.skip_cleanup = skip_cleanup
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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        })
        self.session.cookies.update(cookies)
        web_page = self.session.get('https://open.spotify.com/').text
        token = re.search(r'accessToken":"(.*?)"', web_page).group(1)
        self.session.headers.update({
            'authorization': f'Bearer {token}',
        })


    def get_download_queue(self, url):
        spotify_id = url.split('/')[-1].split('?')[0]
        download_queue = []
        if 'track' in url:
            response = self.session.get(f'https://api.spotify.com/v1/tracks/{spotify_id}').json()
            download_queue.append({
                'gid': TrackId.from_uri(response['uri']).get_gid().hex(),
                'title': response['name']
            })
        elif 'album' in url:
            response = self.session.get(f'https://api.spotify.com/v1/albums/{spotify_id}?limit=100').json()
            for track in response['tracks']['items']:
                download_queue.append({
                    'gid': TrackId.from_uri(track['uri']).get_gid().hex(),
                    'title': track['name']
                })
            if response['tracks']['next'] is not None:
                next_page = response['tracks']['next']
                while True:
                    if next_page is None:
                        break
                    response = self.session.get(next_page).json()
                    for track in response['items']:
                        download_queue.append({
                            'gid': TrackId.from_uri(track['uri']).get_gid().hex(),
                            'title': track['name']
                    })
                    next_page = response['next']
        elif 'playlist' in url:
            response = self.session.get(f'https://api.spotify.com/v1/playlists/{spotify_id}').json()
            for track in response['tracks']['items']:
                download_queue.append({
                    'gid': TrackId.from_uri(track['track']['uri']).get_gid().hex(),
                    'title': track['track']['name']
                })
            if response['tracks']['next'] is not None:
                next_page = response['tracks']['next']
                while True:
                    if next_page is None:
                        break
                    response = self.session.get(next_page).json()
                    for track in response['items']:
                        download_queue.append({
                            'gid': TrackId.from_uri(track['track']['uri']).get_gid().hex(),
                            'title': track['track']['name']
                    })
                    next_page = response['next']
        if not download_queue:
            raise Exception()
        return download_queue
    

    def get_metadata(self, gid):
        return self.session.get(f'https://spclient.wg.spotify.com/metadata/4/track/{gid}?market=from_token').json()
    

    def get_album_id(self, metadata):
        return TrackId.from_hex(metadata['album']['gid']).to_spotify_uri().split(':')[-1]
    

    def get_track_id(self, metadata):
        return metadata['canonical_uri'].split(':')[-1]


    def get_file_id(self, metadata):
        return [metadata["file_id"] for metadata in metadata["file"] if metadata["format"] == self.audio_quality][0]
    

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
    

    def get_artist(self, spotify_artist):
        if len(spotify_artist) == 1:
            return spotify_artist[0]['name']
        artist = ', '.join([artist['name'] for artist in spotify_artist][:-1])
        artist += f' & {spotify_artist[-1]["name"]}'
        return artist


    def get_tags(self, album_id, metadata):
        response = self.session.get(f'https://api.spotify.com/v1/albums/{album_id}').json()
        copyright = [response['text'] for response in response['copyrights'] if response['type'] == 'P']
        if response['release_date_precision'] == 'year':
            release_date = response['release_date'] + '-01-01'
        else:
            release_date = response['release_date']
        if response['tracks']['next'] is None:
            total_tracks = [response['track_number'] for response in response['tracks']['items'] if response['disc_number'] == metadata['disc_number']][-1]
            total_discs = response['tracks']['items'][-1]['disc_number']
        else:
            next_page = response['tracks']['next']
            while True:
                if next_page is None:
                    break
                response = self.session.get(next_page).json()
                total_tracks = [response['track_number'] for response in response['items'] if response['disc_number'] == metadata['disc_number']][-1]
                total_discs = response['items'][-1]['disc_number']
                next_page = response['next']
        tags = {
            '\xa9nam': [metadata['name']],
            '\xa9ART': [self.get_artist(metadata['artist'])],
            'aART': [self.get_artist(metadata['album']['artist'])],
            '\xa9alb': [metadata['album']['name']],
            'trkn': [(metadata['number'], total_tracks)],
            'disk': [(metadata['disc_number'], total_discs)],
            '\xa9day': [f'{release_date}T00:00:00Z'],
            'covr': [
                MP4Cover(
                    self.session.get('https://i.scdn.co/image/' + [metadata['file_id'] for metadata in metadata['album']['cover_group']['image'] if metadata['size'] == 'LARGE'][0]).content,
                    imageformat = MP4Cover.FORMAT_JPEG
                )
            ],
            '\xa9cmt': [f'https://open.spotify.com/track/{metadata["canonical_uri"].split(":")[-1]}'],
            'cprt': copyright,
            'rtng': [0] if metadata.get('explicit') is None else [1]
        }
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
        subprocess.check_output([
            'mp4decrypt',
            encrypted_location,
            '--key',
            keys,
            decrypted_location
        ])
    

    def fixup(self, decrypted_location, fixed_location):
        subprocess.check_output([
            'MP4Box',
            '-add',
            decrypted_location,
            '-itags',
            'album=placeholder',
            '-new',
            '-quiet',
            fixed_location
        ])
    

    def make_final(self, fixed_location, final_location, tags):
        final_location.parent.mkdir(parents = True, exist_ok = True)
        shutil.copy(fixed_location, final_location)
        file = MP4(final_location).tags
        for key, value in tags.items():
            file[key] = value
        file.save(final_location)
    

    def cleanup(self):
        if self.temp_path.exists() and not self.skip_cleanup:
            shutil.rmtree(self.temp_path)


if __name__ == '__main__':
    if not shutil.which('mp4decrypt'):
        raise Exception('mp4decrypt is not on PATH')
    if not shutil.which('MP4Box'):
        raise Exception('MP4Box is not on PATH')
    parser = argparse.ArgumentParser(
        description = 'A Python script to download Spotify songs/albums/playlists.',
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
        help = 'Print Execeptions while downloading.'
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
        args.skip_cleanup
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
            print(f'Downloading "{track["title"]}" (track {j + 1} from URL {i + 1})...')
            try:
                metadata = dl.get_metadata(track['gid'])
                file_id = dl.get_file_id(metadata)
                stream_url = dl.get_stream_url(file_id)
                pssh = dl.get_pssh(file_id)
                decryption_keys = dl.get_decryption_keys(pssh)
                track_id = dl.get_track_id(metadata)
                encrypted_location = dl.get_encrypted_location(track_id)
                dl.download(encrypted_location, stream_url)
                decrypted_location = dl.get_decrypted_location(track_id)
                dl.decrypt(decryption_keys, encrypted_location, decrypted_location)
                fixed_location = dl.get_fixed_location(track_id)
                dl.fixup(decrypted_location, fixed_location)
                album_id = dl.get_album_id(metadata)
                tags = dl.get_tags(album_id, metadata)
                final_location = dl.get_final_location(tags)
                dl.make_final(fixed_location, final_location, tags)
            except KeyboardInterrupt:
                exit(1)
            except:
                error_count += 1
                print(f'* Failed to download "{track["title"]}" (track {j + 1} from URL {i + 1}).')
                if args.print_exceptions:
                    traceback.print_exc()
            dl.cleanup()
    print(f'Done ({error_count} error(s)).')
