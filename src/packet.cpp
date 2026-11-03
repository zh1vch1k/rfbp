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
    packet.seq_num = static_cast<uint8_t>(session_cnt->cnt & 0xFF);
    session_cnt->cnt++;
    packet.crc8 = crc8;
    
    return packet;
}


std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen, 
                                          const SpeckContext_t *ctx, SpeckSessionCounter_t *session_cnt) {
    if (!rxBuf || rxLen < sizeof(LoraRxFrame_t)) {
        return std::nullopt;
    }

    const LoraRxFrame_t* packet = reinterpret_cast<const LoraRxFrame_t*>(rxBuf);
    if (packet->payload_len != sizeof(LoraPayload_t)) {
        return std::nullopt;
    }

    // 1. СНАЧАЛА проверяем CRC8 от сырых зашифрованных байт
    const uint8_t* raw_payload = reinterpret_cast<const uint8_t*>(&(packet->payload));
    uint8_t crc_payload = CRC8_calc(raw_payload, packet->payload_len);
    if (crc_payload != packet->crc8) {
        return std::nullopt; // Пакет побит помехой в эфире
    }

    LoraRxFrame_t result = *packet;

    // 2. Восстанавливаем 32-битный счётчик из 8-битного seq_num с защитой от переполнения
    uint8_t expected_seq = static_cast<uint8_t>(session_cnt->cnt & 0xFF);
    uint8_t diff = static_cast<uint8_t>(result.seq_num - expected_seq);

    // Если разница >= 128 и счетчик уже ненулевой — это устаревший пакет или атака повтора (replay)
    if (diff >= 128 && session_cnt->cnt > 0) {
        return std::nullopt;
    }

    uint32_t target_cnt = session_cnt->cnt + diff;

    SpeckSessionCounter_t decrypt_session;
    decrypt_session.session_id = session_cnt->session_id;
    decrypt_session.cnt = target_cnt;

    // 3. Расшифровываем
    uint8_t* dec_data = reinterpret_cast<uint8_t*>(&(result.payload));
    speck_ctr_crypt(ctx, &decrypt_session, dec_data, result.payload_len);  

    session_cnt->cnt = target_cnt + 1;
    return result;
}