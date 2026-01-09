import time
import signal
from confluent_kafka import Producer

# ==================================================
# CONFIGURAZIONE PRODUCER
# ==================================================

BOOTSTRAP_SERVERS = "localhost:9092"   # <--- Cambia in kafka:9093 se giri da container
TOPIC = "hfgw_lnf"

TARGET_MB_PER_SEC = 80
MESSAGE_SIZE_BYTES = 1000  # messaggi da 1 KB

BYTES_PER_MB = 1024 * 1024
TARGET_BYTES_PER_SEC = TARGET_MB_PER_SEC * BYTES_PER_MB

payload = b"x" * MESSAGE_SIZE_BYTES


def delivery_report(err, msg):
    if err:
        print(f"Errore invio: {err}")


def create_producer():
    return Producer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "acks": "1",
        "compression.type": "lz4",
        "queue.buffering.max.kbytes": 1024 * 1024,   # 1 GB di buffer
        "queue.buffering.max.messages": 2_000_000,
        "batch.num.messages": 10_000,
        "linger.ms": 5,
    })


def main():
    producer = create_producer()

    stop = False

    def handle_stop(sig, frame):
        nonlocal stop
        stop = True
        print("\nInterruzione, flush finale...")

    signal.signal(signal.SIGINT, handle_stop)

    sent_interval = 0
    sent_total = 0
    interval_start = time.perf_counter()

    print(f"Producer avviato: {TARGET_MB_PER_SEC} MB/s target")

    while not stop:
        now = time.perf_counter()
        elapsed = now - interval_start

        # statistiche ogni secondo
        if elapsed >= 1.0:
            mbsec = (sent_interval / BYTES_PER_MB) / elapsed
            total_mb = sent_total / BYTES_PER_MB

            print(f"[STAT] {mbsec:8.2f} MB/s | totale inviato: {total_mb:.2f} MB")

            interval_start = now
            sent_interval = 0

        try:
            producer.produce(TOPIC, payload, callback=delivery_report)
        except BufferError:
            producer.poll(0.1)
            continue

        sent_interval += MESSAGE_SIZE_BYTES
        sent_total += MESSAGE_SIZE_BYTES

        # controllo velocità (rate limiter)
        now = time.perf_counter()
        elapsed = now - interval_start

        if elapsed > 0:
            current_bps = sent_interval / elapsed
            if current_bps > TARGET_BYTES_PER_SEC * 1.05:
                time.sleep(0.001)  # 1ms

        producer.poll(0)

    producer.flush()
    print("Terminato.")


if __name__ == "__main__":
    main()
