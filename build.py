"""Build a Kodi-installable ZIP from the tracked add-on source tree."""
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

base = Path(__file__).resolve().parent
metadata = ET.parse(base / 'addon.xml').getroot()
output = base / 'dist'
output.mkdir(exist_ok=True)
package = output / ('%s-%s.zip' % (metadata.get('id'), metadata.get('version')))
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
    files = [base / name for name in ('addon.xml', 'service.py', 'default.py', 'README.md', 'icon.png')]
    files += [p for p in (base / 'resources').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    for path in sorted(files):
        archive.write(path, metadata.get('id') + '/' + path.relative_to(base).as_posix())
print(package)
