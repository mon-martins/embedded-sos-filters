/* Apply filter_order10 to a whole array, processing one sample at a time.
 *
 * Same result as the block variant, but exercises the per-sample API
 * (sos_process) the way a real-time ISR would call it.
 */
#include "sos_filter.h"
#include "filters_coeffs.h"

static const float32_t coeffs[] = FILTER_SOS_FILTER_ORDER10_COEFFS;
static float32_t state[2 * FILTER_SOS_FILTER_ORDER10_N_SECTIONS];

void apply_filter_order10_sample(const float32_t *in, float32_t *out, size_t n)
{
    sos_filt_t f;
    sos_init(&f, coeffs, state, FILTER_SOS_FILTER_ORDER10_N_SECTIONS);
    for (size_t i = 0; i < n; ++i) {
        out[i] = sos_process(&f, in[i]);
    }
}
