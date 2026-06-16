/* Apply filter_order4 to a whole array using the block API.
 *
 * Coefficients come from the generated header (codegen output); this mirrors
 * how firmware would pair filters_coeffs.h with the runtime library. Each call
 * re-inits (clears) the state, so the array is filtered from a zero history.
 */
#include "sos_filter.h"
#include "filters_coeffs.h"

static const float32_t coeffs[] = FILTER_SOS_FILTER_ORDER4_COEFFS;
static float32_t state[2 * FILTER_SOS_FILTER_ORDER4_N_SECTIONS];

void apply_filter_order4_block(const float32_t *in, float32_t *out, size_t n)
{
    sos_filt_t f;
    sos_init(&f, coeffs, state, FILTER_SOS_FILTER_ORDER4_N_SECTIONS);
    sos_process_block(&f, in, out, n);
}
