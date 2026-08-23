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


LoraTxFrame_t encodePacket(const LoraPayload_t& payload, uint8_t addh, uint8_t addl, uint8_t channel, uint8_t mode,
                           const SpeckContext_t *ctx, SpeckSessionCounter_t *session_cnt) {
    LoraTxFrame_t packet{}; 
    packet.payload = payload;

    uint8_t *data = reinterpret_cast<uint8_t*>(&packet.payload);
    speck_ctr_crypt(ctx, session_cnt, data, sizeof(payload));

    uint8_t crc8 = CRC8_calc(data, sizeof(payload));

    packet.addh = addh;
    packet.addl = addl;
    packet.channel = channel;
    packet.payload_len = sizeof(payload);
    packet.mode = mode & 0x07;
    packet.seq_num = session_cnt->cnt++;
    packet.crc8 = crc8;
    
    return packet;
}


std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen, 
                                          const SpeckContext_t *ctx , SpeckSessionCounter_t *session_cnt) {
    if (rxLen < sizeof(LoraRxFrame_t)) {
        return std::nullopt;
    }
    
    const LoraRxFrame_t* packet = reinterpret_cast<const LoraRxFrame_t*>(rxBuf);
    
    if (packet->payload_len != sizeof(LoraPayload_t)) {
        return std::nullopt;
    }

    const uint8_t* data = reinterpret_cast<const uint8_t*>(&(packet->payload));

    uint8_t crc_payload = CRC8_calc(data, packet->payload_len);

    if (crc_payload != packet->crc8) {
        return std::nullopt;
    }

    LoraRxFrame_t result = *packet;

    SpeckSessionCounter_t decrypt_session = *session_cnt;
    decrypt_session.cnt = result.seq_num;

    uint8_t* dec_data = reinterpret_cast<uint8_t*>(&(result.payload));
    speck_ctr_crypt(ctx, &decrypt_session, dec_data, sizeof(result.payload));  
    session_cnt->cnt = result.seq_num;

    return result;
}