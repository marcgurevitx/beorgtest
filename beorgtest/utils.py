import hashlib


BYTE_BLOCK = 4096


def calc_file_hash(path):
    """
    Calculate hash of file's content
    """
    sha256 = hashlib.sha256()
    with open(str(path), "rb") as f:
        while True:
            block = f.read(BYTE_BLOCK)
            if len(block) == 0:
                break
            sha256.update(block)
    return sha256.hexdigest()
