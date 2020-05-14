import amqp
import click


@click.command()
@click.argument("exchange_id")
@click.option("--broker")
def client(exchange_id, broker):
    
    if broker:
        c = amqp.Connection(host=broker)
    else:
        c = amqp.Connection()
    
    with c:
        ch = c.channel()
        queue, *_ = ch.queue_declare(exclusive=True)
        ch.queue_bind(queue, exchange=exchange_id)
        ch.basic_consume(queue=queue, callback=lambda m: print_changed_file(ch, m))
        
        print(f"Listening to { exchange_id }")
        print("(Ctrl+C to stop)\n")
        
        while True:
            c.drain_events()


def print_changed_file(ch, message):
    """
    Print the name of changed file
    """
    print(f"File { message.body } has been changed, created or deleted")
    ch.basic_ack(message.delivery_tag)
