"""Fetch the pinned CC0 rain-scene assets once; renders themselves stay offline."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

ROOT = Path(os.environ.get('RENDER_STUDIO_ASSETS') or Path(__file__).resolve().parent / 'assets')
HEADERS = {'User-Agent': 'ModVisionLocalRender/1.0 (CC0 asset setup)'}


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=90)


def fetch(record, path):
    path = path.resolve()
    if not path.is_relative_to(ROOT.resolve()) or urlparse(record['url']).hostname != 'dl.polyhaven.org':
        raise ValueError('Unexpected asset path or source')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or hashlib.md5(path.read_bytes()).hexdigest() != record['md5']:
        with request(record['url']) as response:
            data = response.read()
        if hashlib.md5(data).hexdigest() != record['md5']:
            raise RuntimeError('Asset checksum mismatch: ' + path.name)
        temporary = path.with_suffix(path.suffix + '.download')
        temporary.write_bytes(data)
        temporary.replace(path)
    print(path.name, path.stat().st_size, flush=True)


def main():
    ROOT.mkdir(exist_ok=True)
    manifest = ROOT / 'manifest.json'
    if manifest.is_file():
        # A checkout carries exact URLs/checksums; do not silently upgrade its
        # lighting or geometry when upstream files change.
        for record in json.loads(manifest.read_text(encoding='utf-8')):
            fetch(record, ROOT / record['file'])
        return
    records = []
    for asset, choices in [('cloudy_vondelpark', [('hdri', '4k', 'hdr'), ('hdri', '8k', 'hdr')]),
                           ('asphalt_02', [('Diffuse', '2k', 'jpg'), ('nor_gl', '2k', 'jpg'), ('Rough', '2k', 'jpg'),
                                           ('Displacement', '2k', 'exr')])]:
        with request('https://api.polyhaven.com/files/' + asset) as response:
            listing = json.load(response)
        for kind, size, extension in choices:
            record = listing[kind][size][extension]
            path = ROOT / f'{asset}_{kind}_{size}.{extension}'
            fetch(record, path)
            records.append({'file': path.name, 'source': 'https://polyhaven.com/a/' + asset,
                            'url': record['url'], 'license': 'CC0', 'md5': record['md5']})
    for asset in ('tree_small_02', 'grass_medium_01'):
        with request('https://api.polyhaven.com/files/' + asset) as response:
            listing = json.load(response)
        model = listing['gltf']['1k']['gltf']
        resources = {asset + '_1k.gltf': model, **model['include']}
        for relative, record in resources.items():
            path = ROOT / asset / relative
            fetch(record, path)
            records.append({'file': path.relative_to(ROOT).as_posix(), 'source': 'https://polyhaven.com/a/' + asset,
                            'url': record['url'], 'license': 'CC0', 'md5': record['md5']})
    manifest.write_text(json.dumps(records, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
