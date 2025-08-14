import io
import functools
import binascii
import filetype
from base64 import b64encode, b64decode
from pathlib import Path


def _guess_content_type(raw):
    guessed_type = filetype.guess(raw)
    return guessed_type.mime


def _parsed_content(raw, find_content_type, base_64_encode):
    content_type = _guess_content_type(raw) if find_content_type else None
    parsed_content = b64encode(raw).decode() if base_64_encode else raw
    return parsed_content, content_type


@functools.singledispatch
def parse_content(content, find_content_type=False, base_64_encode=True):
    raise TypeError(
        '\n'.join([
            f'Could not parse content {content} of type {type(content)}',
            'Specify content by using one of the options below:',
            '1. Path to a file either as a string or as a Path object',
            '2. Bytes object with b64encoding',
            '3. Bytes object without b64encoding',
            '4. IO Stream of either bytes or text',
        ])
    )


@parse_content.register(str)
@parse_content.register(Path)
def _(content, find_content_type=False, base_64_encode=True):
    raw = Path(content).read_bytes()
    return _parsed_content(raw, find_content_type, base_64_encode)


@parse_content.register(bytes)
@parse_content.register(bytearray)
def _(content, find_content_type=False, base_64_encode=True):
    try:
        raw = b64decode(content, validate=True)
    except binascii.Error:
        raw = content
    return _parsed_content(raw, find_content_type, base_64_encode)


@parse_content.register(io.IOBase)
def _(content, find_content_type=False, base_64_encode=True):
    raw = content.read()
    raw = raw.encode() if isinstance(raw, str) else raw
    return _parsed_content(raw, find_content_type, base_64_encode)
