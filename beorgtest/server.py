import hashlib
import os
import pathlib
import time
import uuid

import amqp
import click


CHECKS_PER_SECOND = 1/2
BYTE_BLOCK = 4096


@click.command()
@click.option("--dir", required=True,
              type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--rate", default=CHECKS_PER_SECOND)
@click.option("--broker")
def server(dir, rate, broker):
    path = pathlib.Path(dir)
    sleep_seconds = 1 / rate
    hashes = {}
    unique_exchange = str(uuid.uuid4())
    if broker:
        c = amqp.Connection(host=broker)
    else:
        c = amqp.Connection()
    with c:
        ch = c.channel()
        ch.exchange_declare(exchange=unique_exchange, type="fanout")
        
        print(f"Start monitoring { path }")
        print(f"Exchange ID for client connection:  { unique_exchange }")
        print("(Ctrl+C to stop)\n")
        
        while True:
            changed = check_dir(path, hashes)
            for file_path in changed:
                ch.basic_publish(amqp.Message(str(file_path)), exchange=unique_exchange)
            time.sleep(sleep_seconds)


def check_dir(path, hashes):
    """
    Traverse `path` and compare the hashes of files with previously calculated.
    Return paths that changed.
    The `hashes` dict is modified in place.
    """
    old_files = set(hashes)
    changed = []
    for root, dirs, files in os.walk(str(path)):
        root_path = pathlib.Path(root)
        for name in files:
            file_path = root_path / name
            old_files -= { file_path }
            file_hash = calc_hash(file_path)
            if file_hash == hashes.get(file_path):
                continue
            print(f"File { file_path } has been changed or created")
            changed.append(file_path)
            hashes[file_path] = file_hash
    deleted = list(old_files)
    for file_path in deleted:
        del hashes[file_path]
        print(f"File { file_path } has been deleted")
    return changed + deleted


def calc_hash(path):
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
