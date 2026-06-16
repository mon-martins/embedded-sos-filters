/*
 * Stand-in for the MCU basic types used by the compile tests.
 *
 * On a real build these come from the MCU device support / standard library;
 * this header is a host substitute so the portable C source compiles under
 * gcc. NOT part of the library.
 */
#ifndef MCU_TYPES_H
#define MCU_TYPES_H

#include <stdint.h>   /* uint8_t */
#include <stddef.h>   /* size_t */

typedef float float32_t;

#endif /* MCU_TYPES_H */
