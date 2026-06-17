/**
 * @file    sos_filter_cla.h
 * @brief   CLA (TI C2000 Control Law Accelerator) variant of the SOS DF2T
 *          filter meant to run on the CLA coprocessor.
 */
#ifndef SOS_FILTER_CLA_H
#define SOS_FILTER_CLA_H

#ifdef SOS_FILTER_H
#error "sos_filter.h must not be included with sos_filter_cla.h"
#endif

#include "cla_types.h"

#define SOS_COEFFS_PER_SECTION 5u
#define SOS_STATE_PER_SECTION  2u

typedef struct {
    const float32_t *coeffs;  /**< 5 coeffs per section: b0,b1,b2,a1,a2 */
    float32_t       *state;   /**< 2 states per section (zeroed on init) */
    uint16_t         n_sections;
} sos_filt_t;

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Initialize the instance and clear the state (runs on the CLA). */
void sos_cla_init(sos_filt_t *f, const float32_t *coeffs,
                  float32_t *state, uint16_t n_sections);

/** @brief Clear the internal state, keeping the coefficients (runs on the CLA). */
void sos_cla_reset(sos_filt_t *f);

/** @brief Process one sample on the CLA. Returns the filtered output. */
float32_t sos_cla_process(sos_filt_t *f, float32_t x);

/** @brief Process a block on the CLA (in and out may alias). */
void sos_cla_process_block(sos_filt_t *f, const float32_t *in,
                           float32_t *out, uint16_t n);

#ifdef __cplusplus
}
#endif

#endif /* SOS_FILTER_CLA_H */
