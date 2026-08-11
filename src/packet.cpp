#include "packet.hpp"

uint8_t CRC8_calc(const uint8_t *data, uint8_t dataLength) {
    uint8_t crc8 = 0x00;
    
    while (dataLength--) {
        crc8 ^= *data++;

        for (uint8_t i = 0; i<8; i++) {
            if (crc8 & 0x80) {
                crc8 = (crc8 << 1) ^ 0x07;
            }
            else { 
                crc8 <<= 1;
            }
        }
    }
    return crc8;
}


LoraTxFrame_t encodePacket(const LoraPayload_t& payload, uint8_t addh, uint8_t addl, uint8_t channel, uint8_t mode) {
    uint8_t dataLen = sizeof(payload);
    const uint8_t *data = reinterpret_cast<const uint8_t*>(&payload);

    uint8_t crc8 = CRC8_calc(data, dataLen);

    LoraTxFrame_t packet{};

    packet.addh = addh;
    packet.addl = addl;
    packet.channel = channel;
    packet.payload_len = dataLen;
    packet.mode = mode & 0x07;
    packet.payload = payload;
    packet.crc8 = crc8;

    return packet;
}


std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen) {

    if (rxLen < sizeof(LoraRxFrame_t)) {
        return std::nullopt;
    }

    const LoraRxFrame_t* packet = reinterpret_cast<const LoraRxFrame_t*>(rxBuf);

    if (packet->payload_len != sizeof(LoraPayload_t)) {
        return std::nullopt;
    }
    const uint8_t *data = reinterpret_cast<const uint8_t*>(&(packet->payload));
    uint8_t crc_payload = CRC8_calc(data, packet->payload_len);

    if (crc_payload != packet->crc8) {
        return std::nullopt;
    }

    return *packet;
}