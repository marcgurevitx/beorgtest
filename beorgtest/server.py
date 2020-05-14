import json
import logging
import os
import os.path
import socket
import uuid

import amqp
import click

from . import utils


CHECKS_PER_SECOND = 1/2


class DirMonitorer:
    """
    Object to keep business data together, separate from AMQP stuff.
    """
    
    def __init__(self, dir, rate):
        self.dir = dir
        self.delay_seconds = 1 / rate
        self.hashes = {}
    
    def full_state(self, ch, req_msg):
        """
        Callback for full-state exchange
        """
        logging.info("Replying to full state request...")
        
        rep_json = json.dumps(list(self.hashes))
        rep_msg = amqp.Message(
            rep_json,
            content_type="application/json",
            correlation_id=req_msg.correlation_id,
        )
        ch.basic_publish(
            rep_msg,
            exchange="",
            routing_key=req_msg.reply_to,
        )
        ch.basic_ack(req_msg.delivery_tag)
    
    def publish_updates(self, ch, exchange_out):
        """
        Publish updates
        """
        logging.debug("Checking dir...")
        
        added, deleted, modified = self.detect_changes()
        if len(added) + len(deleted) + len(modified) > 0:
            logging.info("Dir changed, sending update...")
            msg_json = json.dumps({
                "added": added,
                "deleted": deleted,
                "modified": modified,
            })
            msg = amqp.Message(
                msg_json,
                content_type="application/json",
            )
            ch.basic_publish(
                msg,
                exchange=exchange_out,
            )
    
    def detect_changes(self):
        """
        Return 3 lists of file names (added, deleted, modified) corresponding to
        changes in dir
        """
        added, deleted, modified = [], [], []
        
        visited_set = set()
        for root, dirs, files in os.walk(self.dir):
            for name in files:
                path = os.path.join(root, name)
                hash = utils.calc_file_hash(path)
                if path not in self.hashes:
                    added.append(path)
                    logging.debug("Added file %s", path)
                elif self.hashes[path] != hash:
                    modified.append(path)
                    logging.debug("Modified file %s", path)
                self.hashes[path] = hash
                visited_set.add(path)
        
        deleted.extend(set(self.hashes) - visited_set)
        for path in deleted:
            del self.hashes[path]
            logging.debug("Deleted file %s", path)
        return added, deleted, modified


@click.command()
@click.option("--dir", required=True,
              type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--rate", default=CHECKS_PER_SECOND)
@click.option("--broker")
@click.option("--log", "loglevel", default="INFO")
def server(dir, rate, broker, loglevel):
    """
    The server CLI. See README.
    """
    logging.basicConfig(level=loglevel.upper())
    
    monitorer = DirMonitorer(dir, rate)  # no such word...
    print(f"  Monitoring { dir } ...")
    
    server_id = str(uuid.uuid4())
    print(f"  Server ID for client connection:  { server_id }")
    
    exchange_in = f"{ server_id }-in"
    exchange_out = f"{ server_id }-out"
    
    if broker:
        c = amqp.Connection(host=broker)
    else:
        c = amqp.Connection()
    with c:
        ch = c.channel()
        
        # Setup full-state exchange and queue
        ch.exchange_declare(exchange=exchange_in, type="fanout")
        queue_in, *_ = ch.queue_declare(exclusive=True)
        ch.queue_bind(queue_in, exchange=exchange_in)
        ch.basic_consume(queue=queue_in, callback=lambda msg: monitorer.full_state(ch, msg))
        
        # Setup updates exchange
        ch.exchange_declare(exchange=exchange_out, type="fanout")
        
        print("  (Ctrl+C to stop)\n")
        while True:
            
            # Reply to full-state requests (why does it raise?... i don't get it...)
            try:
                c.drain_events(timeout=monitorer.delay_seconds)
            except socket.timeout:
                pass
            
            # Publish updates
            monitorer.publish_updates(ch, exchange_out)
