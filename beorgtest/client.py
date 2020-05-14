import json
import logging
import socket
import uuid

import amqp
import click


STATE_TIMEOUT = 4.0  # seconds


class RemoteState:
    def __init__(self):
        self.file_names = []
        self.ready = False
    
    def init(self, ch, message):
        """
        Callback for server's full state reply
        """
        logging.info("Received full state...")
        assert message.content_type == "application/json"
        self.file_names = json.loads(message.body)
        self.file_names.sort()
        self.print_dir()
        self.ready = True
        ch.basic_ack(message.delivery_tag)
    
    def on_update(self, ch, message):
        """
        Callback for server's updates
        """
        logging.info("Received update...")
        assert message.content_type == "application/json"
        update = json.loads(message.body)
        for path in update["added"]:
            logging.debug("Added %s", path)
            self.file_names.append(path)
        for path in update["deleted"]:
            logging.debug("Deleted %s", path)
            self.file_names.remove(path)
        for path in update["modified"]:
            logging.debug("Modified %s", path)
        self.file_names.sort()
        self.print_dir()
        ch.basic_ack(message.delivery_tag)
    
    def print_dir(self):
        """
        Print remote files list
        """
        print("  New directory state:")
        for path in self.file_names:
            print(f"    { path }")


@click.command()
@click.argument("server_id")
@click.option("--broker")
@click.option("--log", "loglevel", default="INFO")
def client(server_id, broker, loglevel):
    """
    The client CLI. See README.
    """
    logging.basicConfig(level=loglevel.upper())
    
    remote_state = RemoteState()
    exchange_in = f"{ server_id }-in"
    exchange_out = f"{ server_id }-out"
    
    if broker:
        c = amqp.Connection(host=broker)
    else:
        c = amqp.Connection()
    with c:
        ch = c.channel()
        
        # Setup queue for server's full state relpy
        state_queue, *_ = ch.queue_declare(exclusive=True)
        ch.basic_consume(queue=state_queue, callback=lambda msg: remote_state.init(ch, msg))
        
        # Request full state
        logging.info("Requesting state...")
        msg = amqp.Message(
            correlation_id=str(uuid.uuid4()),  # maybe we don't need it...
            reply_to=state_queue,
        )
        ch.basic_publish(msg, exchange=exchange_in)
        while not remote_state.ready:
            try:
                c.drain_events(timeout=STATE_TIMEOUT)
            except socket.timeout:
                logging.debug("No full state reply...")
        
        
        # FIXME: We're probably losing updates from the server right now
        
        
        # Setup queue for server's updates
        updates_queue, *_ = ch.queue_declare(exclusive=True)
        ch.queue_bind(updates_queue, exchange=exchange_out)
        ch.basic_consume(queue=updates_queue, callback=lambda msg: remote_state.on_update(ch, msg))
        
        # Listen to updates
        logging.info("Listening to updates...")
        print("  (Ctrl+C to stop)\n")
        while True:
            c.drain_events()
