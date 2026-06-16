/**
 * @file    sos_filter.h
 * @brief   Cascaded second-order sections (SOS) IIR filter,
 *          Direct Form II Transposed (DF2T), float32.
 *
 * Portable C API suitable for embedded targets (ARM Cortex-M, TI C2000, ...).
 *
 * Coefficient layout (matches the generated filters_coeffs.h):
 *   5 coefficients per section, denominator normalized to a0 = 1:
 *     coeffs[5*i + 0] = b0
 *     coeffs[5*i + 1] = b1
 *     coeffs[5*i + 2] = b2
 *     coeffs[5*i + 3] = a1
 *     coeffs[5*i + 4] = a2
 *
 * State (DF2T): 2 delay variables per section -> state[2*n_sections].
 */

#ifndef SOS_FILTER_H
#define SOS_FILTER_H

#ifdef SOS_FILTER_CLA_H
#error "sos_filter_cla.h must not be included with sos_filter.h"
#endif

#include "mcu_types.h"

#define SOS_COEFFS_PER_SECTION 5u
#define SOS_STATE_PER_SECTION  2u

typedef struct {
    const float32_t *coeffs;  /**< 5 coeffs per section: b0,b1,b2,a1,a2 */
    float32_t       *state;   /**< 2 states per section (zeroed on init) */
    uint8_t          n_sections;
} sos_filt_t;

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize the instance and clear the state.
 * @param coeffs      buffer with 5*n_sections coefficients (see layout).
 * @param state       buffer with 2*n_sections floats (will be zeroed).
 * @param n_sections  number of second-order sections.
 */
void sos_init(sos_filt_t *f, const float32_t *coeffs,
              float32_t *state, uint8_t n_sections);

/** @brief Clear the internal state (history), keeping the coefficients. */
void sos_reset(sos_filt_t *f);

/** @brief Process one sample and return the filtered output. */
float32_t sos_process(sos_filt_t *f, float32_t x);

/** @brief Process a block (in and out may alias the same buffer). */
void sos_process_block(sos_filt_t *f, const float32_t *in,
                       float32_t *out, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* SOS_FILTER_H */
