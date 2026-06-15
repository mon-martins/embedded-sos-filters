/*
 * Stand-in for the C28x basic types used by the compile tests.
 *
 * On a real build these come from the TI device support / standard library;
 * this header is a host substitute so the portable C source compiles under
 * gcc. NOT part of the library.
 */
#ifndef C28X_TYPES_H
#define C28X_TYPES_H

#include <stdint.h>   /* uint8_t */
#include <stddef.h>   /* size_t */

typedef float float32_t;

#endif /* C28X_TYPES_H */
