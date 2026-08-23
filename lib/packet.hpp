#pragma once

#include <iostream>
#include <cstdint>
#include <optional>
#include "speck.hpp"

#pragma pack(push, 1)

typedef struct {
    uint32_t st_l_ax_x        : 7;
    uint32_t st_l_ax_y        : 7;
    uint32_t st_r_ax_x        : 7;
    uint32_t st_r_ax_y        : 7;
    uint32_t reserved_buttons : 4;
    uint8_t  trigger_l        : 4;
    uint8_t  trigger_r        : 4;
} LoraPayload_t;

typedef struct {
    uint8_t       addh;
    uint8_t       addl;
    uint8_t       channel;
    uint8_t       payload_len : 5;
    uint8_t       mode        : 3;
    uint8_t       seq_num;
    LoraPayload_t payload;
    uint8_t       crc8;
} LoraTxFrame_t;

typedef struct {
    uint8_t       payload_len : 5;
    uint8_t       mode        : 3;
    uint8_t       seq_num;
    LoraPayload_t payload;
    uint8_t       crc8;
} LoraRxFrame_t;

#pragma pack(pop)


uint8_t CRC8_calc(const uint8_t *data, uint8_t dataLength);

LoraTxFrame_t encodePacket(const LoraPayload_t& payload, uint8_t addh, uint8_t addl, uint8_t channel, uint8_t mode,
                           const SpeckContext_t *ctx, SpeckSessionCounter_t *session_cnt);

std::optional<LoraRxFrame_t> decodePacket(const uint8_t *rxBuf, uint8_t rxLen, 
                                          const SpeckContext_t *ctx , SpeckSessionCounter_t *session_cnt);