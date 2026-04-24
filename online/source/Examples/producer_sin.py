import numpy as np
import time
import signal
from confluent_kafka import Producer

# ==========================
# CONFIG KAFKA
# ==========================
BOOTSTRAP_SERVERS = "localhost:9092"   # oppure "kafka:9093" se sei in Docker
TOPIC = "hfgw_lnf"

# ==========================
# CONFIG SINUSOIDI
# ==========================
NUM_CHANNELS = 8
FS = 1_000_000            # sample rate simbolico
BLOCK_SAMPLES = 50_000    # campioni per blocco (~800 kB per blocco)
INT16_MAX = 32767

# Frequenze delle 8 sinusoidi (Hz)
FREQUENCIES = [
    10_000, 20_000, 30_000, 40_000,
    50_000, 60_000, 70_000, 80_000
]

# Ampiezze diverse per ogni sinusoide (0.0–1.0)
AMPLITUDES = [
    0.20, 0.35, 0.50, 0.65,
    0.80, 0.90, 0.60, 0.30
]

assert len(FREQUENCIES) == NUM_CHANNELS
assert len(AMPLITUDES) == NUM_CHANNELS


# ==========================
# CREAZIONE PRODUCER
# ==========================
def create_producer():
    return Producer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "acks": "1",
        "compression.type": "lz4",
        "queue.buffering.max.kbytes": 1024 * 1024,
        "queue.buffering.max.messages": 2_000_000,
        "batch.num.messages": 10_000,
        "linger.ms": 5,
    })


# ==========================
# GENERAZIONE BLOCCHI
# ==========================
def generate_block(phases):
    """
    Genera BLOCK_SAMPLES campioni per ciascuno degli 8 canali,
    con ampiezze e frequenze diverse.
    Restituisce:
      - dati interleaved int16
      - fasi aggiornate
    """
    t = np.arange(BLOCK_SAMPLES, dtype=np.float64) / FS  # tempo relativo del blocco

    signals = []
    for i in range(NUM_CHANNELS):
        f = FREQUENCIES[i]
        A = AMPLITUDES[i]

        s = A * np.sin(phases[i] + 2 * np.pi * f * t)
        signals.append(s)

    # Aggiorna fase per il blocco successivo
    for i in range(NUM_CHANNELS):
        phases[i] += 2 * np.pi * FREQUENCIES[i] * BLOCK_SAMPLES / FS
        # Evita overflow numerico
        phases[i] = np.mod(phases[i], 2 * np.pi)

    # shape: (8, BLOCK_SAMPLES)
    data = np.stack(signals, axis=0)

    # Converti in int16
    data_int16 = np.round(data * INT16_MAX).astype("<i2")

    # Interleave: (C, N) → (N, C) → flatten
    interleaved = data_int16.T.reshape(-1)

    return interleaved, phases


# ==========================
# PRODUCER LOOP
# ==========================
def delivery_report(err, msg):
    if err:
        print(f"Errore invio: {err}")


def main():
    producer = create_producer()

    phases = np.zeros(NUM_CHANNELS, dtype=np.float64)
    stop = False

    def handle_stop(sig, frame):
        nonlocal stop
        stop = True
        print("\nInterruzione richiesta, termino...")

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    bytes_interval = 0
    total_bytes = 0
    interval_start = time.perf_counter()
    block_index = 0

    print(f"Producer infinito avviato sul topic '{TOPIC}'")
    print("Sinusoidi con ampiezze diverse generazione continua...")

    while not stop:
        # genera blocco
        block, phases = generate_block(phases)
        payload = block.tobytes()
        block_size = len(payload)

        # manda al broker
        try:
            producer.produce(
                TOPIC,
                value=payload,
                key=str(block_index).encode("ascii"),
                callback=delivery_report,
            )
        except BufferError:
            producer.poll(0.5)
            producer.produce(
                TOPIC,
                value=payload,
                key=str(block_index).encode("ascii"),
                callback=delivery_report,
            )

        producer.poll(0)

        bytes_interval += block_size
        total_bytes += block_size
        block_index += 1
        time.sleep(0.005)
        now = time.perf_counter()
        elapsed = now - interval_start

        # statistiche ogni ~1 s
        if elapsed >= 1.0:
            mb_sec = bytes_interval / (1024*1024) / elapsed
            total_mb = total_bytes / (1024*1024)
            print(f"[STAT] {mb_sec:8.2f} MB/s | inviati: {total_mb:,.2f} MB")

            bytes_interval = 0
            interval_start = time.perf_counter()

    print("Flush finale...")
    producer.flush()
    print("Terminato.")


if __name__ == "__main__":
    main()
