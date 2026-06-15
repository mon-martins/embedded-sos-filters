/**
 * @file  sos_filter.c
 * @brief Cascaded SOS IIR filter, Direct Form II Transposed, float32.
 *        Portable C implementation.
 */
#include "sos_filter.h"

void sos_init(sos_filt_t *f, const float32_t *coeffs,
              float32_t *state, uint8_t n_sections)
{
    f->coeffs = coeffs;
    f->state = state;
    f->n_sections = n_sections;
    sos_reset(f);
}

void sos_reset(sos_filt_t *f)
{
    const size_t n = (size_t)f->n_sections * SOS_STATE_PER_SECTION;
    for (size_t i = 0; i < n; ++i) {
        f->state[i] = 0.0f;
    }
}

float32_t sos_process(sos_filt_t *f, float32_t x)
{
    const float32_t *c = f->coeffs;
    float32_t *s = f->state;

    for (uint8_t i = 0; i < f->n_sections; ++i) {
        const float32_t b0 = c[0];
        const float32_t b1 = c[1];
        const float32_t b2 = c[2];
        const float32_t a1 = c[3];
        const float32_t a2 = c[4];

        /* Direct Form II Transposed:
         *   y    = b0*x + s0
         *   s0'  = b1*x - a1*y + s1
         *   s1'  = b2*x - a2*y
         */
        const float32_t y = b0 * x + s[0];
        s[0] = b1 * x - a1 * y + s[1];
        s[1] = b2 * x - a2 * y;

        x = y;       /* output of this section feeds the next */
        c += SOS_COEFFS_PER_SECTION;
        s += SOS_STATE_PER_SECTION;
    }
    return x;
}

void sos_process_block(sos_filt_t *f, const float32_t *in,
                       float32_t *out, size_t n)
{
    for (size_t k = 0; k < n; ++k) {
        out[k] = sos_process(f, in[k]);
    }
}
