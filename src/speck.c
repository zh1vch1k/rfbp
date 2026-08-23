#include "speck.hpp"
#include <string.h>

#define ROR32(x, r) (((x) >> (r)) | ((x) << (32 - (r))))
#define ROL32(x, r) (((x) << (r)) | ((x) >> (32 - (r))))
#define SPECK_ROUND(x, y, k) (x = (ROR32(x, 8) + y) ^ (k), y = ROL32(y, 3) ^ (x))

void speck_init(SpeckContext_t *ctx, const uint8_t key[16]) {
    uint32_t k[4];
    memcpy(k, key, 16);

    ctx->round_keys[0] = k[0];
    uint32_t l[3] = { k[1], k[2], k[3] };

    for (uint32_t i = 0; i < 26; i++) {
        uint32_t *target = &l[i % 3];
        uint32_t y = ctx->round_keys[i];
        SPECK_ROUND(*target, y, i);
        ctx->round_keys[i + 1] = y;
    }
}

void speck_encrypt_block(const SpeckContext_t *ctx, const uint32_t in[2], uint32_t out[2]) {
    uint32_t y = in[0];
    uint32_t x = in[1];

    for (int i = 0; i < 27; i++) {
        SPECK_ROUND(x, y, ctx->round_keys[i]);
    }

    out[0] = y;
    out[1] = x;
}

void speck_ctr_crypt(const SpeckContext_t *ctx, const SpeckSessionCounter_t *session_cnt, uint8_t *data, size_t len) {
    uint32_t block_in[2];
    uint32_t block_out[2];
    uint64_t nonce = ((uint64_t)session_cnt->session_id << 32) | session_cnt->cnt;

    memcpy(block_in, &nonce, 8);
    speck_encrypt_block(ctx, block_in, block_out);

    uint8_t *keystream = (uint8_t*)block_out;
    for (size_t i = 0; i < len; i++) {
        data[i] ^= keystream[i];
    }
}