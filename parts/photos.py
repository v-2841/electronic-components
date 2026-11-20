from io import BytesIO
from pathlib import PurePosixPath
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image


MAX_BYTES = 15 * 1024 * 1024
TIMEOUT = 15
# some shops answer bots with an error page: look like a browser
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
EXTENSIONS = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}


def download_photo(url):
    """Image by URL as a file for Part.photo; ValidationError with a
    message for the user when it cannot be had."""
    if urlparse(url).scheme not in ('http', 'https'):
        raise ValidationError('Нужна ссылка, начинающаяся с http:// или '
                              'https://.')
    request = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            data = response.read(MAX_BYTES + 1)
    except (URLError, OSError, ValueError) as error:
        reason = getattr(error, 'reason', error)
        raise ValidationError(f'Не удалось скачать картинку: {reason}.')
    if len(data) > MAX_BYTES:
        raise ValidationError('Картинка больше 15 МБ.')
    try:
        image = Image.open(BytesIO(data))
        image.verify()
    except Exception:
        raise ValidationError('По ссылке не картинка (нужен JPEG, PNG, '
                              'WebP или GIF).')
    stem = PurePosixPath(unquote(urlparse(url).path)).stem or 'photo'
    extension = EXTENSIONS.get(image.format, (image.format or 'img').lower())
    return ContentFile(data, name=f'{stem[:80]}.{extension}')
