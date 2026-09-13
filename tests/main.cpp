#include <iostream>
#include "packet.hpp"
#include "speck.hpp"
#include "key.hpp"


int main() {
    SpeckContext_t crypto_ctx = {};
    SpeckSessionCounter_t tx_cnt = {1010, 0};
    SpeckSessionCounter_t rx_cnt = {1010, 0};

    LoraPayload_t tx_payload{};

    speck_init(&crypto_ctx, RFBP_SECRET_KEY);
    
    tx_payload.st_l_ax_x = 64;
    tx_payload.st_l_ax_y = 120;
    tx_payload.trigger_l = 8;

    LoraTxFrame_t tx_frame = encodePacket(tx_payload, 0x00, 0x01, 0x04, 0x02, &crypto_ctx, &tx_cnt);

    const uint8_t* rx_stream = reinterpret_cast<const uint8_t*>(&tx_frame) + 3;
    uint8_t rx_bytes_count = sizeof(LoraTxFrame_t) - 3; 

    
    auto rx_result = decodePacket(rx_stream, rx_bytes_count, &crypto_ctx, &rx_cnt);

    if (rx_result.has_value()) {
        std::cout << "[SUCCESS] Packet decoded!\n";
        std::cout << "Mode: " << (int)rx_result->mode << "\n";
        std::cout << "Stick X: " << (int)rx_result->payload.st_l_ax_x << "\n";
    } else {
        std::cout << "[ERROR] Decode failed!\n";
    }

    return 0;
}