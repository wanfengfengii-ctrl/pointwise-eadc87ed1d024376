import os
from pathlib import Path
import tempfile

from spectral.archive.codec import encode_payload
from spectral.archive.reading import read, read_parent_chain


def export(catalog, direction_id, destination):
    root = read(catalog, direction_id)
    if root["kind"] != "direction":
        raise ValueError("export requires a direction artifact")
    package = {"format_version": 1, "direction_id": direction_id,
               "chain": read_parent_chain(catalog, direction_id)}
    destination = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=destination.parent,
                                         prefix=".spectral-", delete=False) as stream:
            temporary = stream.name
            stream.write(encode_payload(package))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return destination
