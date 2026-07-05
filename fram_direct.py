import smbus2
import time
import json
import os
from dev_mode import DEV_MODE, note_mock

I2C_BUS = 1
FRAM_ADDRESS = 0x50  # I2C-Adresse des FM24CL64B

try:
    bus = smbus2.SMBus(I2C_BUS)
except Exception as e:
    if not DEV_MODE:
        raise
    print(f"[DEV MODE] Kein I2C-Bus verfuegbar ({e}), FRAM-Zugriffe nutzen direkt den Mock.")
    bus = None

_MOCK_STORE_PATH = os.path.join(os.path.dirname(__file__), "dev_fram_store.json")
_mock_store = None


def _load_mock_store():
    global _mock_store
    if _mock_store is None:
        if os.path.exists(_MOCK_STORE_PATH):
            with open(_MOCK_STORE_PATH, "r") as f:
                _mock_store = {int(k): v for k, v in json.load(f).items()}
        else:
            _mock_store = {}
    return _mock_store


def _save_mock_store():
    with open(_MOCK_STORE_PATH, "w") as f:
        json.dump(_mock_store, f)


def _mock_write_bytes(address, data):
    store = _load_mock_store()
    for offset, byte in enumerate(data):
        store[address + offset] = byte
    _save_mock_store()


def _mock_read_bytes(address, length):
    store = _load_mock_store()
    return bytes(store.get(address + offset, 0) for offset in range(length))


def _seed_mock_store():
    """On first DEV_MODE run, seed the mock FRAM from Lepmon_config.json so
    hardware.get_hardware_version() and friends resolve without hitting
    their JSON-fallback path."""
    if os.path.exists(_MOCK_STORE_PATH):
        return
    try:
        # Read Lepmon_config.json directly (not via json_read_write) since
        # that module itself imports from fram_direct - going through it
        # here would risk a circular import depending on import order.
        config_path = os.path.join(os.path.dirname(__file__), "Lepmon_config.json")
        with open(config_path, "r") as f:
            general = json.load(f).get("general", {})
        arni_gen = general.get("ARNI_Gen") or ""
        sn = general.get("serielnumber") or ""
        _mock_write_bytes(0x0130, arni_gen.ljust(16)[:16].encode("utf-8"))
        _mock_write_bytes(0x0110, sn.ljust(8)[:8].encode("utf-8"))
    except Exception as e:
        print(f"[DEV MODE] Konnte Mock-FRAM nicht aus Lepmon_config.json vorbefüllen: {e}")


def _real_read_bytes(address: int, length: int) -> bytes:
    if bus is None:
        raise OSError("kein I2C-Bus verfuegbar")
    result = bytearray()
    for offset in range(length):
        high = ((address + offset) >> 8) & 0xFF
        low = (address + offset) & 0xFF
        bus.write_i2c_block_data(FRAM_ADDRESS, high, [low])
        result.append(bus.read_byte(FRAM_ADDRESS))
    return bytes(result)


def _real_write_bytes(address: int, data) -> None:
    if bus is None:
        raise OSError("kein I2C-Bus verfuegbar")
    for offset, byte in enumerate(data):
        high = ((address + offset) >> 8) & 0xFF
        low = (address + offset) & 0xFF
        bus.write_i2c_block_data(FRAM_ADDRESS, high, [low, byte])


def check_fram_present():
    try:
        sn = read_fram(0x0110, 8).strip()
        print(f"RAM Modul des ARNI {sn} gefunden")
        return True #True
    except Exception as e:
        print("RAM dieses ARNI nicht verfügbar")
        return False


def write_fram(address: int, data):
    """
    Schreibt einen String oder Bytes byteweise an eine Adresse (max 64 kB FRAM).

    Speicherstruktur (Adressbereiche, Nutzung):
    ┌────────────┬─────┬──────────────────────────────────────────────────────┐
    │ Bereich    │ Gr. │ Beschreibung                                         │
    ├────────────┼─────┼──────────────────────────────────────────────────────┤
    │ 0x0000-00FF│ 256 │ Powersave: Timestamps, Status, Regime Raspi/ATtiny   │
    │ 0x0100-0BFF│6912 │ Laufzeitdaten & Logging Raspi                        │
    │ 0x1C00-1FFF│1024 │ Seriennummer, Kalibrierung, Versionen, Produktion    │
    └────────────┴─────┴──────────────────────────────────────────────────────┘
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if DEV_MODE:
        try:
            _real_write_bytes(address, data)
            return
        except OSError:
            note_mock("FRAM (FM24CL64B)")
            _mock_write_bytes(address, data)
            return
    try:
        _real_write_bytes(address, data)
        #print(f"{data} geschrieben an 0x{address:04X}")
    except OSError as e:
        print(f"Fehler beim Schreiben von 0x{address:04X}: {e}")


def read_fram(address: int, length: int) -> str:
    """Liest eine feste Anzahl Bytes ab Adresse und gibt als String zurück."""
    if DEV_MODE:
        try:
            return _real_read_bytes(address, length).decode(errors="ignore").strip()
        except OSError:
            note_mock("FRAM (FM24CL64B)")
            return _mock_read_bytes(address, length).decode(errors="ignore").strip()
    try:
        decoded = _real_read_bytes(address, length).decode(errors="ignore").strip()
        #print(f"Gelesen von 0x{address:04X} (Länge {length}): '{decoded}'")
        return decoded
    except OSError as e:
        print(f"Fehler beim Lesen von 0x{address:04X}: {e}")
        return None


def write_fram_bytes(address: int, data: bytes):
    """
    Schreibt ein Bytes-Objekt byteweise an eine Adresse (max 64 kB FRAM).
    """
    if DEV_MODE:
        try:
            _real_write_bytes(address, data)
            return
        except OSError:
            note_mock("FRAM (FM24CL64B)")
            _mock_write_bytes(address, data)
            return
    try:
        _real_write_bytes(address, data)
        #print(f"{data} (bytes) geschrieben an 0x{address:04X}")
    except OSError as e:
        print(f"Fehler beim Schreiben von 0x{address:04X}: {e}")


def dump_fram(start=0x00, length=0x80):
    """Hexdump des FRAM von Startadresse für gegebene Länge."""
    print("\n Speicher-Dump:")
    for i in range(start, start + length, 16):
        hex_line = ""
        ascii_line = ""
        for j in range(16):
            addr = i + j
            try:
                val = _real_read_bytes(addr, 1)[0]
            except OSError:
                if DEV_MODE:
                    note_mock("FRAM (FM24CL64B)")
                    val = _mock_read_bytes(addr, 1)[0]
                else:
                    val = 0x00
            hex_line += f"{val:02X} "
            ascii_line += chr(val) if 32 <= val <= 126 else "."
        print(f"{i:04X}: {hex_line:<48} {ascii_line}")


def read_fram_bytes(address: int, length: int) -> bytes:
    """
    Liest eine feste Anzahl Bytes ab Adresse und gibt sie als bytes-Objekt zurück.
    """
    if DEV_MODE:
        try:
            return _real_read_bytes(address, length)
        except OSError:
            note_mock("FRAM (FM24CL64B)")
            return _mock_read_bytes(address, length)
    try:
        result = _real_read_bytes(address, length)
        #print(f"Gelesen (bytes) von 0x{address:04X} (Länge {length}): {result.hex()}")
        return result
    except OSError as e:
        print(f"Fehler beim Lesen von 0x{address:04X}: {e}")
        return None


if DEV_MODE:
    _seed_mock_store()

if __name__ == "__main__":
    print ("teste RAM")
    check_fram_present()
    print("FRAM-Dump:")

    dump_fram(0x0000, 0x09EF)
