/**
 * @file  Rte_Types.h
 * @brief AUTOSAR base type definitions
 * @swc   SpeedSensor
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#ifndef RTE_TYPES_H
#define RTE_TYPES_H

#include <stdint.h>

/* AUTOSAR primitive type definitions (R22-11) */
typedef unsigned char        uint8;
typedef unsigned short       uint16;
typedef unsigned int         uint32;
typedef signed char          sint8;
typedef signed short         sint16;
typedef float                float32;

/* Standard return type */
typedef unsigned char  Std_ReturnType;
#define E_OK     ((Std_ReturnType)0x00U)
#define E_NOT_OK ((Std_ReturnType)0x01U)

/* Implementation types for SpeedSensor */
typedef uint16               uint16_T;

#endif /* RTE_TYPES_H */
