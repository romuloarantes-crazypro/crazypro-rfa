"""Teste de fumaça do app em execução: sobe, processa uma foto e confere os metadados."""
import io, sys, time
import piexif, requests
from PIL import Image

base = 'http://127.0.0.1:8080'
s = requests.Session()
for _ in range(60):
    try:
        if s.get(base + '/health', timeout=3).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(2)
else:
    sys.exit('o app não respondeu em 2 minutos')

assert 'ExifBoost Pro' in s.get(base + '/').text, 'tela inicial sem o nome do app'
buf = io.BytesIO()
Image.new('RGB', (400, 300), 'red').save(buf, 'JPEG')
r = s.post(base + '/upload', files={'files': ('teste.jpg', buf.getvalue(), 'image/jpeg')})
r.raise_for_status()
nome = r.json()['files'][0]['name']
r = s.post(base + '/apply', json={'files': [nome], 'meta': {'desc': 'Teste', 'artist': 'RFA', 'gmn_resize': '0', 'lat': '-26.45', 'lon': '-49.1'}})
r.raise_for_status()
res = r.json()['results'][0]
assert res['ok'], res
saida = s.get(f"{base}/download_file/{r.json()['sid']}/{res['out']}")
assert saida.status_code == 200, saida.status_code
exif = piexif.load(saida.content)
assert exif['0th'][piexif.ImageIFD.Software] == b'ExifBoost Pro', 'Software incorreto'
assert piexif.GPSIFD.GPSLatitude in exif['GPS'], 'GPS não gravado'
print('TESTE DE FUMACA OK')
