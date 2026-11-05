# RFBP — Radio Fast Bitmap Protocol

```
                                              █▓▓▒▒░
v1.3.0                                         ███▓▒▒░
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

**RFBP (Radio Fast Bitmap Protocol)** is a lightweight, bit-packed binary protocol for sending controller input (sticks, triggers, buttons) and telemetry over a radio link (LoRa). It features a modular controller input adapter supporting **PS DualSense**, **Xbox (XInput/Series/One)**, and **generic gamepads** on the transmitting side, targeting **STM32/ESP32** microcontrollers on the receiving side.

The over-the-air radio frame (`LoraRxFrame_t`) is strictly sized at **8 bytes (64 bits)** — matching the block size of the underlying **Speck64/128 CTR** stream cipher for zero-padding authenticated encryption, single-cycle keystream generation, and minimal LoRa Time-on-Air.

## Packet format

### Header

| Field | Size | Description |
|---|---|---|
| `LoRa ADDH` | 8 bit | High byte of the LoRa receiver address (Tx frame only) |
| `LoRa ADDL` | 8 bit | Low byte of the LoRa receiver address (Tx frame only) |
| `LoRa channel` | 8 bit | LoRa channel used to open the session (Tx frame only) |
| `payload length` | 5 bit | Fixed payload length (5 bytes per protocol specification) |
| `mode` | 3 bit | Bitmask selecting active system modes (camera, drivers, lights, etc.) |
| `seq_num` | 8 bit | Monotonic packet counter (used for Nonce derivation & replay protection) |

### Payload (`LoraPayload_t` — 40 bit / 5 bytes)

| Field | Size | Range | Description |
|---|---|---|---|
| `st_l_ax_x` | 7 bit | 0–127 | Left stick, X axis (neutral: 64) |
| `st_l_ax_y` | 7 bit | 0–127 | Left stick, Y axis (neutral: 64) |
| `st_r_ax_x` | 7 bit | 0–127 | Right stick, X axis (neutral: 64) |
| `st_r_ax_y` | 7 bit | 0–127 | Right stick, Y axis (neutral: 64) |
| `reserved_buttons` | 4 bit | 0–15 | 4-button bitmask (`L3`, `R3`, `L1/LB`, `R1/RB`) |
| `trigger_l` | 4 bit | 0–15 | Left trigger (released: 0, fully pressed: 15) |
| `trigger_r` | 4 bit | 0–15 | Right trigger (released: 0, fully pressed: 15) |

> Universally normalized via the built-in adapter module for **PS DualSense**, **Xbox**, and **Generic HID** gamepads.

### Footer

| Field | Size | Description |
|---|---|---|
| `CRC8` | 8 bit | Checksum of raw encrypted payload (polynomial `0x07`, Encrypt-then-MAC) |

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
├── CMakeLists.txt        # Build config (static library + test binary)
├── lib/
│   ├── adapter.hpp       # Controller input adapter (DualSense, Xbox, Generic)
│   ├── fsm.hpp           # Radio state machine & session handshake frames
│   ├── key.hpp           # Pre-shared encryption keys & session salts
│   ├── packet.hpp        # Bit-packed frame structs, CRC8, encode/decode
│   ├── speck.hpp         # Speck64/128 block cipher & CTR mode interface
│   └── telemetry.hpp     # GNSS (NMEA GNRMC), power & IMU telemetry structures
├── src/
│   ├── adapter.cpp       # Normalization, deadzone suppression & axis scaling
│   ├── fsm.cpp           # Handshake frame encoding & verification
│   ├── packet.cpp        # CRC8, encodePacket(), decodePacket() with replay filter
│   ├── speck.cpp         # Speck64/128 block cipher implementation
│   └── telemetry.cpp     # Compact NMEA GNRMC string parser
├── tests/
│   └── main.cpp          # Automated test suite (rollover, packet drop, replay attack)
└── tools/
    └── visualizer.py     # Interactive Protocol Inspector & Live Telemetry HUD (Pygame)
```

**Language:** C++17, header/impl split, zero external dependencies — only the C++ STL (`<cstdint>`, `<optional>`, `<cmath>`, `<algorithm>`).

## Core modules

### 1. Packet encoding & decoding (`lib/packet.hpp`)

All structures are `#pragma pack(push, 1)` packed to ensure binary wire portability:

- `LoraPayload_t` — the 5-byte bit-packed stick/trigger/button payload.
- `LoraTxFrame_t` — transmitter frame: LoRa routing address (`addh`, `addl`, `channel`), header, encrypted payload, CRC8.
- `LoraRxFrame_t` — receiver over-the-air frame (strictly **8 bytes / 64 bits**): mode/len byte, `seq_num`, encrypted payload, CRC8.

```cpp
uint8_t CRC8_calc(const uint8_t *data, uint8_t dataLength);

LoraTxFrame_t encodePacket(const LoraPayload_t& payload, uint8_t addh, uint8_t addl, 
                           uint8_t channel, uint8_t mode,
                           const SpeckContext_t *ctx, SpeckSessionCounter_t *session_cnt);

std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen, 
                                          const SpeckContext_t *ctx, SpeckSessionCounter_t *session_cnt);
```

### 2. Controller adapter (`lib/adapter.hpp`)

Normalizes analog axes, applies deadzone filtering before transmission to eliminate stick drift, and maps physical triggers/buttons across controller vendors into `LoraPayload_t`:

```cpp
namespace rfbp::adapter {

enum class ControllerType : uint8_t {
    NORMALIZED = 0, // Sticks [-1.0 .. 1.0], triggers [0.0 .. 1.0]
    DUALSENSE,      // PlayStation: Triggers [-1.0 .. 1.0]
    XBOX,           // Xbox / XInput: Triggers [0.0 .. 1.0]
    GENERIC         // Generic HID / Digital trigger buttons
};

enum class ButtonMask : uint8_t {
    BTN_L_STICK  = (1 << 0), // L3 / LS click
    BTN_R_STICK  = (1 << 1), // R3 / RS click
    BTN_L_BUMPER = (1 << 2), // L1 / LB
    BTN_R_BUMPER = (1 << 3)  // R1 / RB
};

LoraPayload_t adapt(const GamepadState& state, const AdapterConfig& config = {});

} // namespace rfbp::adapter
```

### 3. Security architecture (`lib/speck.hpp`, `src/speck.cpp`)

* **Cipher:** Speck64/128 (NSA lightweight block cipher optimized for 32-bit ARM Cortex-M and RISC-V).
* **Mode of Operation:** Counter (CTR) mode — stream cipher operation without block padding overhead (5 bytes of plaintext produce exactly 5 bytes of ciphertext).
* **Nonce Derivation:** `uint64_t Nonce = ((uint64_t)session_id << 32) | cnt`.
* **Replay Protection & Rollover:** Receiver dynamically reconstructs the 32-bit session counter from the wire 8-bit `seq_num`, dropping stale frames or replays (`diff >= 128`).
* **Integrity:** Encrypt-then-MAC scheme using CRC8 (`poly = 0x07`). Corrupted frames are discarded before any cryptographic operations.

## Build & run

### Requirements

- CMake ≥ 3.12
- C++17 compatible compiler (GCC, Clang, or MSVC)
- C99 compiler for Speck core

On Debian / Ubuntu:

```bash
sudo apt-get install -y cmake build-essential
```

On macOS (Homebrew):

```bash
brew install cmake
```

### Build

```bash
git clone https://github.com/zh1vch1k/rfbp.git
cd rfbp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

This generates:
- `build/librfbp.a` — static library containing packet codecs, cipher, telemetry, and adapter
- `build/rfbp_test` — automated test binary (disable via `-DBUILD_TESTS=OFF`)

### Run tests

```bash
./build/rfbp_test
```

Expected output:

```text
--- Test 1: Sequential 600 packets across 8-bit rollover (0..599) ---
[PASS] 600 packets decoded successfully across rollovers!
--- Test 2: Packet loss across boundary (drop 3 packets) ---
[PASS] Packet loss recovery verified! Correctly synchronized to cnt=604
--- Test 3: Replay attack rejection ---
[PASS] Replay packet successfully rejected!
ALL TESTS PASSED!
```

### Interactive Protocol Inspector (Live HUD)

RFBP includes an interactive telemetry & protocol inspector built with Pygame. It visualizes controller normalization, deadzone suppression, 40-bit bit-packing, Speck64/128 CTR encryption, and the exact 8-byte over-the-air frame in real time.

```bash
pip install pygame
python3 tools/visualizer.py
```

**Features:**
- **Multi-gamepad support:** Auto-detects and adapts **PS DualSense**, **Xbox (XInput)**, and **Generic HID** controllers.
- **Mouse & Demo fallback:** If no gamepad is plugged in, drag sticks with mouse or press `SPACE` for automated sine-wave simulation.
- **Live Wire Frame:** Inspect the 8-byte frame byte-by-byte in glowing HEX and color-coded binary bitstream.
- **Crypto toggle:** Switch between raw plaintext and Speck64/128 ciphertext keystream in real time (`E` key).
- **Mode selection:** Change system modes on the fly (`1-7` keys).

## Integration example

```cmake
# CMakeLists.txt of your project
add_subdirectory(rfbp)
target_link_libraries(your_target PRIVATE rfbp)
```

```cpp
#include "packet.hpp"
#include "adapter.hpp"
#include "speck.hpp"
#include "key.hpp"

// 1. Initialize crypto session
SpeckContext_t crypto_ctx;
speck_init(&crypto_ctx, RFBP_SECRET_KEY);
SpeckSessionCounter_t tx_counter = {/*session_id=*/ 0xABCD1234, /*cnt=*/ 0};

// 2. Read raw controller state & adapt to RFBP payload
rfbp::adapter::GamepadState raw_pad{};
raw_pad.left_x = 0.0f;     // Center
raw_pad.left_y = 0.75f;    // Forward
raw_pad.trigger_r = 1.0f;  // Full throttle

rfbp::adapter::AdapterConfig cfg{};
cfg.type = rfbp::adapter::ControllerType::XBOX;
cfg.deadzone = 0.08f;      // 8% hardware deadzone

LoraPayload_t payload = rfbp::adapter::adapt(raw_pad, cfg);

// 3. Encode & encrypt frame
LoraTxFrame_t tx_frame = encodePacket(payload, 
                                      /*addh=*/ 0x00, /*addl=*/ 0x01, /*channel=*/ 0x17, /*mode=*/ 0x02,
                                      &crypto_ctx, &tx_counter);

// 4. On receiver (e.g. STM32 / ESP32 receiving 8-byte OTA frame):
SpeckSessionCounter_t rx_counter = {/*session_id=*/ 0xABCD1234, /*cnt=*/ 0};
auto rx_frame = decodePacket(rx_buffer, sizeof(LoraRxFrame_t), &crypto_ctx, &rx_counter);

if (rx_frame.has_value()) {
    uint8_t steer = rx_frame->payload.st_l_ax_x; // 64 (neutral)
    uint8_t speed = rx_frame->payload.st_l_ax_y;
}
```

## Use case

RFBP targets embedded remote-control systems (UGVs, robotics, drones) requiring:
- Exact **8-byte over-the-air frames** for low-bitrate radio links (LoRa, FSK, packet radios);
- Seamless multi-controller support (**DualSense, Xbox, Generic HID**);
- Hardware deadzone suppression before transmission to eliminate radio noise;
- Transparent **Speck64/128 CTR** encryption with replay-attack rejection;
- Fast integrity validation via CRC8.
