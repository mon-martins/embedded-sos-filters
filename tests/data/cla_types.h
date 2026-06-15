/*
 * Stand-in for the CLA basic types used by the compile tests.
 *
 * On a real build these come from the TI CLA support headers; this header is a
 * host substitute so the CLA source can be syntax-checked under gcc. NOT part
 * of the library.
 */
#ifndef CLA_TYPES_H
#define CLA_TYPES_H

#include <stdint.h>   /* uint8_t, uint16_t */

typedef float float32_t;

#endif /* CLA_TYPES_H */
