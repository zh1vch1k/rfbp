#pragma once

#include <iostream>
#include <cstdint>
#include <optional>
#include "speck.hpp"

#pragma pack(push, 1)

typedef struct {
    uint8_t       addh;
    uint8_t       addl;
    uint8_t       channel;
    uint32_t      tx_session_salt;
    uint32_t      session_id;
} HandshakeTx_t;

typedef struct {
    uint32_t      rx_session_salt;
    uint32_t      session_id;
} HandshakeRx_t;

#pragma pack(pop)

HandshakeTx_t encodeHandshake(uint8_t addh, uint8_t addl, uint8_t channel, uint32_t session_id, uint32_t expected_salt);

std::optional<HandshakeRx_t> decodeHandshake(const uint8_t *rxBuf, uint8_t rxLen, uint32_t expected_salt);