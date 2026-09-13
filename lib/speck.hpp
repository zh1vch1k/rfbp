#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t round_keys[27];
} SpeckContext_t;

typedef struct {
    uint32_t session_id;
    uint32_t cnt;
} SpeckSessionCounter_t;


void speck_init(SpeckContext_t *ctx, const uint8_t key[16]);

void speck_encrypt_block(const SpeckContext_t *ctx, const uint32_t in[2], uint32_t out[2]);

void speck_ctr_crypt(const SpeckContext_t *ctx, const SpeckSessionCounter_t *session_cnt, uint8_t *data, size_t len);

#ifdef __cplusplus
}
#endif