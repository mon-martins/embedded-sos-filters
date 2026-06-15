/**
 * @file    sos_filter_cla.h
 * @brief   CLA (TI C2000 Control Law Accelerator) variant of the SOS DF2T
 *          filter -- meant to run on the CLA coprocessor.
 *
 * Self-contained: it carries its own type/struct definitions so a CLA build
 * does not need to pull in the portable C API (sos_filter.h). The shared
 * SOS_FILTER_TYPES_DEFINED guard lets both headers coexist in one translation
 * unit without redefinition.
 *
 * Same coefficient/state layout and math as the portable C version. The CLA is
 * single-precision (float32) native, so the filter maps directly.
 *
 * All functions below are leaf functions: none calls another (the cascade is
 * inlined by hand in the block routine). This keeps the CLA call depth at 1
 * from a task, so it works on every CLA compiler version and avoids per-sample
 * call overhead. Recursion is not used (the CLA has no stack).
 *
 * Build: compile lib/source_cla/sos_filter_cla.cla with the TI cl2000
 * compiler using --cla_support (e.g. --cla_support=cla1). The coefficient,
 * state and I/O buffers must live in CLA-accessible RAM.
 */
#ifndef SOS_FILTER_CLA_H
#define SOS_FILTER_CLA_H

/* Shared types, guarded so sos_filter.h and sos_filter_cla.h can both be
 * included in the same translation unit without redefinition. */
#ifndef SOS_FILTER_TYPES_DEFINED
#define SOS_FILTER_TYPES_DEFINED

#define SOS_COEFFS_PER_SECTION 5u
#define SOS_STATE_PER_SECTION  2u

typedef struct {
    const float32_t *coeffs;  /**< 5 coeffs per section: b0,b1,b2,a1,a2 */
    float32_t       *state;   /**< 2 states per section (zeroed on init) */
    uint8_t          n_sections;
} sos_filt_t;

#endif /* SOS_FILTER_TYPES_DEFINED */

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Initialize the instance and clear the state (runs on the CLA). */
void sos_cla_init(sos_filt_t *f, const float32_t *coeffs,
                  float32_t *state, uint8_t n_sections);

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
