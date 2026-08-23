# RFBP — Radio Fast Bitmap Protocol

```
                                              █▓▓▒▒░
v1.1.0                                         ███▓▒▒░
_________________________________________________███▓▓▒▒░                    
░░▒▒▓▓██$$$$$$$\  |$$$$$$$\  |$$$$$$$\  |$$$$$$$\ ███▓▓▓▒▒▒░           
░░▒▒▓▓██$$  __$$\ |$$  ____| |$$  __$$\ |$$  __$$\ ███▓▓▓▓▓▒▒░
░░▒▒▓▓██$$ |  $$ ||$$ |      |$$ |  $$ ||$$ |  $$ | ███▓▓▓▓▓▒▒░░      
░░▒▒▓▓██$$$$$$$  ||$$$$$\    |$$$$$$$  ||$$$$$$$  |  ███▓▓▓▓▓▒▒▒░░░    
░░▒▒▓▓██$$  __$$< |$$  __|   |$$  __$$< |$$  ____/  ███▓▓▓▓▓▒▒░░
░░▒▒▓▓██$$ |  $$ ||$$ |      |$$ |  $$ ||$$ |      ███▓▓▓▓▓▒▒░
░░▒▒▓▓██$$ |  $$ ||$$ |      |$$$$$$$$ ||$$ |     ███▓▓▓▒▒▒░
░░▒▒▓▓██\__|__\___|\__|_______\_______/__\__|____███▓▓▒▒░
                                               ███▓▒▒░
                                              █▓▓▒▒░
```

## About

**RFBP (Radio Fast Bitmap Protocol)** is a lightweight, bit-packed binary protocol for sending controller input (sticks, triggers, buttons) over a radio link (LoRa). It's built around a **PS DualSense** controller on the transmitting side and an **STM32/ESP32** microcontroller on the receiving side.

The library provides simple C++17 primitives to pack controller state into a fixed-size frame, encode it with an address/channel header and a CRC8 checksum, and decode/validate an incoming frame on the receiver.

## Packet format

### Header

| Field | Size | Description |
|---|---|---|
| `LoRa ADDH` | 8 bit | High byte of the LoRa receiver address |
| `LoRa ADDL` | 8 bit | Low byte of the LoRa receiver address |
| `LoRa channel` | 8 bit | LoRa channel used to open the session |
| `payload length` | 5 bit | Fixed payload length (fixed per protocol version) |
| `mode` | 3 bit | Bitmask selecting which system modules are active (camera, drivers, etc.) |
| `seq_num` | 8 bit | Monotonic packet counter (used for Nonce derivation & replay protection) |

### Payload

| Field | Size | Description |
|---|---|---|
| `st_l_ax_x` | 7 bit | Left stick, X axis (0–127) |
| `st_l_ax_y` | 7 bit | Left stick, Y axis (0–127) |
| `st_r_ax_x` | 7 bit | Right stick, X axis (0–127) |
| `st_r_ax_y` | 7 bit | Right stick, Y axis (0–127) |
| `reserved buttons` | 4 bit | Reserved state for 4 buttons (on/off) |
| `trigger_l` | 4 bit | Left trigger (0–15) |
| `trigger_r` | 4 bit | Right trigger (0–15) |

> Designed and tested against a **PS DualSense** controller.

### Footer

| Field | Size | Description |
|---|---|---|
| `CRC packet` | 8 bit | CRC8 checksum of the packet |

```
┌───────────────────────────  HEADER ────────────────────────────┐
│                                                                │
│                 ADDH(8b) │ ADDL(8b) │ channel(8b)              │                  
│          payload_len(5b) │ mode(3b) │ seq_num (8b)             │
│                                                                │
├──────────────────────────── PAYLOAD ───────────────────────────┤
│                                                                │
│ st_l_x(7b) │ st_l_y(7b) │ st_r_x(7b) │ st_r_y(7b) │ buttons(4b)│
│ buttons(4b) │ trigger_l(4b) │ trigger_r(4b)                    │
│                                                                │
├──────────────────────────── FOOTER ────────────────────────────┤
│                                                                │
│ CRC8(8b)                                                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Repository layout

```
rfbp/
├── CMakeLists.txt      # build config (static lib + optional test binary)
├── lib/
│   └── packet.hpp       # packed structs + function declarations
├── src/
│   └── packet.cpp        # CRC8, encodePacket(), decodePacket()
└── tests/
    └── main.cpp           # minimal encode/decode smoke test
```

**Language:** C++17, header/impl split, no external dependencies — just the STL (`<cstdint>`, `<optional>`).

**Core types** (`lib/packet.hpp`), all `#pragma pack(push, 1)`-packed to match the wire format:

- `LoraPayload_t` — the bit-packed stick/trigger/button payload described above.
- `LoraTxFrame_t` — what the transmitter builds: address/channel/mode header + payload + CRC8.
- `LoraRxFrame_t` — what the receiver parses: mode/payload-len + payload + CRC8 (no address/channel, since those are only needed to open the LoRa session, not part of the over-the-air data frame).

**Core functions** (`src/packet.cpp`):

- `uint8_t CRC8_calc(const uint8_t *data, uint8_t dataLength)` — CRC8 with polynomial `0x07`, used to check payload integrity.
- `LoraTxFrame_t encodePacket(const LoraPayload_t& payload, uint8_t addh, uint8_t addl, uint8_t channel, uint8_t mode)` — builds a full TX frame and computes its CRC8.
- `std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen)` — parses raw bytes into an `LoraRxFrame_t`, returns `std::nullopt` if the buffer is too short, the declared payload length doesn't match, or the CRC8 doesn't validate.

**Security architecture** 

* **Cipher:** Speck64/128 (NSA lightweight block cipher optimized for microcontrollers).
* **Mode of Operation:** Counter (CTR) mode — turns the block cipher into an authenticated stream cipher with zero payload padding overhead.
* **Nonce Derivation:** `uint64_t Nonce = ((uint64_t)session_id << 32) | seq_num`.
* **Integrity:** Encrypt-then-MAC scheme using CRC8 (`poly = 0x07`). Corrupted packets are discarded prior to any crypto operations.

**Core crypto functions** (`src/speck.c` / `lib/speck.hpp`):

- `void speck_init(SpeckContext_t *ctx, const uint8_t key[16])` — expands a 128-bit master key into 27 32-bit round keys using the Speck key schedule.
- `void speck_encrypt_block(const SpeckContext_t *ctx, const uint32_t in[2], uint32_t out[2])` — executes 27 rounds of Speck64 block encryption on an input 64-bit block (`in`) and writes the output block to `out`.
- `void speck_ctr_crypt(const SpeckContext_t *ctx, const SpeckSessionCounter_t *session_cnt, uint8_t *data, size_t len)` — derives a 64-bit Nonce from `session_id` and `cnt`, generates a keystream via `speck_encrypt_block()`, and performs in-place XOR encryption/decryption on arbitrary-length buffer `data`.


## Build & run

### Requirements

- CMake ≥ 3.12
- A C++17 compiler (GCC/Clang/MSVC)
- C99 compiler for Speck core

On Debian/Ubuntu:

```bash
sudo apt-get install -y cmake g++
```

### Build

```bash
git clone https://github.com/zh1vch1k/rfbp.git
cd rfbp
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make
```

This produces:
- `librfbp.a` — the static library (`encodePacket`, `decodePacket`, `CRC8_calc`)
- `rfbp_test` — the test binary (built by default; disable with `-DBUILD_TESTS=OFF`)

### Run the test

```bash
./rfbp_test
```

Expected output:

```
[SUCCESS] Packet decoded!
Mode: 2
Stick X: 64
```

### Use as a library

Link `rfbp` into your own CMake target:

```cmake
add_subdirectory(rfbp)
target_link_libraries(your_target PRIVATE rfbp)
```

```cpp
#include "packet.hpp"

LoraPayload_t payload{};
payload.st_l_ax_x = 64;
payload.trigger_l = 8;

LoraTxFrame_t frame = encodePacket(payload, /*addh=*/0x00, /*addl=*/0x01, /*channel=*/0x04, /*mode=*/0x02);

// on the receiver, after opening the LoRa session with (addh, addl, channel):
auto decoded = decodePacket(rx_buffer, rx_len);
if (decoded) {
    // decoded->payload.st_l_ax_x, decoded->mode, ...
}
```

## Use case

RFBP targets remote-control projects (RC vehicles, robotics, etc.) where you need:
- a small packet size for low-bitrate radio links (LoRa);
- flexible module enable/disable via `mode`;
- integrity checking on the receiver side via CRC8.
- inti-replay and over-the-air payload encryption for embedded control loops.

