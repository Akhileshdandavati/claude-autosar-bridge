/**
 * @file  Rte_BrakeActuator.h
 * @brief RTE API for BrakeActuator
 * @swc   BrakeActuator
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#ifndef RTE_BRAKEACTUATOR_H
#define RTE_BRAKEACTUATOR_H

#include "Rte_Types.h"

/* Run5ms */
#define Rte_IWrite_Run5ms_BrakeCommandPort_BrakeTorque(data) \
    (*(float32*)Rte_Inst_BrakeActuator.BrakeCommandPort->BrakeTorque = (data))

#endif /* RTE_BRAKEACTUATOR_H */
