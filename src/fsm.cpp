#include "key.hpp"
#include "fsm.hpp"

HandshakeTx_t encodeHandshake(uint8_t addh, uint8_t addl, uint8_t channel, uint32_t session_id , uint32_t expected_salt) {
    HandshakeTx_t handshake = {};

    handshake.addh = addh;
    handshake.addl = addl;
    handshake.channel = channel;
    handshake.session_id = session_id;
    handshake.tx_session_salt = expected_salt;

    return handshake;
}


std::optional<HandshakeRx_t> decodeHandshake(const uint8_t *rxBuf, uint8_t rxLen, uint32_t expected_salt) {
    if (rxLen < sizeof(HandshakeRx_t) || rxBuf == nullptr) {
        return std::nullopt;
    }

    const auto *pkt = reinterpret_cast<const HandshakeRx_t*>(rxBuf);

    if (pkt->rx_session_salt != expected_salt) {
        return std::nullopt;
    }

    return *pkt;
}