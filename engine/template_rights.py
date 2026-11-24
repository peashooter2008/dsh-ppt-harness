"""Market build guard for excluded media from previously reviewed masters."""

from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

from engine import Deck


RESTRICTED_MEDIA_SIZES = {415202, 5441226, 1667147, 190226, 619109}
RESTRICTED_MEDIA_DIGESTS = {
    "ba97d9deef119184b50f350cb6df4075788c7abe55c18b1d9946b391145ce213",
    "9b33833c5363bfca30614a6afe8a8adf4e6922c01f4d4ea5b58a806934b1b883",
    "241602b105ba0000d97756737e40383c51c397cc4a0b84a46711ccfc331be84d",
    "aa656d2f44ca28912bd31329b6ef09ed97c2c6758cebac7fa9983798797547e1",
    "0f751e1bbd99ace69d7cbf58a92b6eaa6213aaaa42f555a10ea5291c996b5d15",
}


def replace_restricted_photo(data):
    """Keep approved decks unchanged and reject known excluded original media."""
    with ZipFile(BytesIO(data)) as package:
        candidates = [entry.filename for entry in package.infolist()
                      if entry.file_size in RESTRICTED_MEDIA_SIZES]
    if candidates:
        # Validate the archive's resource limits before reading candidate payloads.
        with Deck(data).zip as package:
            if any(sha256(package.read(name)).hexdigest() in RESTRICTED_MEDIA_DIGESTS
                   for name in candidates):
                raise ValueError("这份原稿包含不应沿用的媒体，请改用已审核的社区版，或先清除对应素材。")
    return data
