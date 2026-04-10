/**
 * @file  Rte_CanGateway.h
 * @brief RTE API for CanGateway
 * @swc   CanGateway
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#ifndef RTE_CANGATEWAY_H
#define RTE_CANGATEWAY_H

#include "Rte_Types.h"

/* Run1ms */
#define Rte_IRead_Run1ms_EngineSpeedIn_EngineSpeed() \
    (*(uint16*)Rte_Inst_CanGateway.EngineSpeedIn->EngineSpeed)

#define Rte_IRead_Run1ms_ThrottleIn_ThrottlePosition() \
    (*(uint8*)Rte_Inst_CanGateway.ThrottleIn->ThrottlePosition)

#define Rte_IWrite_Run1ms_EngineSpeedOut_EngineSpeedFwd(data) \
    (*(uint16*)Rte_Inst_CanGateway.EngineSpeedOut->EngineSpeedFwd = (data))

#define Rte_IWrite_Run1ms_ThrottleOut_ThrottlePositionFwd(data) \
    (*(uint8*)Rte_Inst_CanGateway.ThrottleOut->ThrottlePositionFwd = (data))

#endif /* RTE_CANGATEWAY_H */
