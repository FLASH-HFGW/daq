#!/etc/python3

from kafka import KafkaProducer
from kafka.errors import KafkaError
import time
import numpy as np
import json
import socket
name = socket.gethostbyname(socket.gethostname())

# Configurazione del producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',  # Modifica con il tuo broker Kafka
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

topic = "hfgw_lnf"

def on_success(metadata):
    print(f"Message produced to topic '{metadata.topic}' at offset {metadata.offset}")

def on_error(e):
    print(f"Error sending message: {e}")

# Produce asynchronously with callbacks

n=0
try:
   while True:
      t = time.time()
      a = np.array(np.random.normal(0, 5, 1024)).tolist()
      payload = {
        "time": time.time(),
        "stream": a
      }

      future = producer.send(topic, value=payload)
      if n%100==0:
         print("data id:", n, name)
         future.add_callback(on_success)
         future.add_errback(on_error)
      producer.flush()
      n+=1

except KeyboardInterrupt:
    print("Interrotto dall'utente. Chiusura del producer...")
finally:
    producer.close()
