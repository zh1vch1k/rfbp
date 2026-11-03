#include <iostream>
#include "packet.hpp"
#include "speck.hpp"
#include "key.hpp"


int main() {
    SpeckContext_t crypto_ctx = {};
    SpeckSessionCounter_t tx_cnt = {0x12345678, 0};
    SpeckSessionCounter_t rx_cnt = {0x12345678, 0};

    speck_init(&crypto_ctx, RFBP_SECRET_KEY);

    std::cout << "--- Test 1: Sequential 600 packets across 8-bit rollover (0..599) ---\n";
    for (uint32_t i = 0; i < 600; ++i) {
        LoraPayload_t tx_payload{};
        tx_payload.st_l_ax_x = (i * 7) % 128;
        tx_payload.st_l_ax_y = (i * 13) % 128;
        tx_payload.trigger_l = i % 16;
        tx_payload.trigger_r = (i * 3) % 16;

        LoraTxFrame_t tx_frame = encodePacket(tx_payload, 0x00, 0x01, 0x17, 0x02, &crypto_ctx, &tx_cnt);

        const uint8_t* rx_stream = reinterpret_cast<const uint8_t*>(&tx_frame) + 3;
        uint8_t rx_bytes_count = sizeof(LoraTxFrame_t) - 3;

        auto rx_result = decodePacket(rx_stream, rx_bytes_count, &crypto_ctx, &rx_cnt);
        if (!rx_result.has_value()) {
            std::cout << "[ERROR] Decode failed at packet i=" << i << "!\n";
            return 1;
        }

        if (rx_result->payload.st_l_ax_x != tx_payload.st_l_ax_x ||
            rx_result->payload.st_l_ax_y != tx_payload.st_l_ax_y ||
            rx_result->payload.trigger_l != tx_payload.trigger_l) {
            std::cout << "[ERROR] Payload mismatch at packet i=" << i << "!\n";
            return 1;
        }
    }
    std::cout << "[PASS] 600 packets decoded successfully across rollovers!\n";

    std::cout << "--- Test 2: Packet loss across boundary (drop 3 packets) ---\n";
    // We are at tx_cnt = 600. Let's send packet 600, 601, 602 (drop them), and send 603.
    LoraPayload_t tx_dummy{};
    encodePacket(tx_dummy, 0x00, 0x01, 0x17, 0x02, &crypto_ctx, &tx_cnt); // 600
    encodePacket(tx_dummy, 0x00, 0x01, 0x17, 0x02, &crypto_ctx, &tx_cnt); // 601
    encodePacket(tx_dummy, 0x00, 0x01, 0x17, 0x02, &crypto_ctx, &tx_cnt); // 602

    LoraPayload_t tx_603{};
    tx_603.st_l_ax_x = 99;
    LoraTxFrame_t tx_frame_603 = encodePacket(tx_603, 0x00, 0x01, 0x17, 0x02, &crypto_ctx, &tx_cnt); // 603
    const uint8_t* rx_stream_603 = reinterpret_cast<const uint8_t*>(&tx_frame_603) + 3;

    auto rx_603 = decodePacket(rx_stream_603, sizeof(LoraTxFrame_t) - 3, &crypto_ctx, &rx_cnt);
    if (!rx_603.has_value() || rx_603->payload.st_l_ax_x != 99) {
        std::cout << "[ERROR] Packet loss recovery failed!\n";
        return 1;
    }
    std::cout << "[PASS] Packet loss recovery verified! Correctly synchronized to cnt=604\n";

    std::cout << "--- Test 3: Replay attack rejection ---\n";
    // Replay old packet 603 again
    auto rx_replay = decodePacket(rx_stream_603, sizeof(LoraTxFrame_t) - 3, &crypto_ctx, &rx_cnt);
    if (rx_replay.has_value()) {
        std::cout << "[ERROR] Replayed packet was accepted!\n";
        return 1;
    }
    std::cout << "[PASS] Replay packet successfully rejected!\n";

    std::cout << "ALL TESTS PASSED!\n";
    return 0;
}