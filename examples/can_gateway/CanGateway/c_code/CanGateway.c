/**
 * @file  CanGateway.c
 * @brief Runnable implementations for CanGateway
 * @swc   CanGateway
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#include "CanGateway.h"

/**
 * CanGateway_Run1ms — Periodic — every 1ms
 * reads EngineSpeedIn.EngineSpeed (uint16)
 * reads ThrottleIn.ThrottlePosition (uint8)
 * writes EngineSpeedOut.EngineSpeedFwd (uint16)
 * writes ThrottleOut.ThrottlePositionFwd (uint8)
 */
void CanGateway_Run1ms(void)
{
    uint16 EngineSpeed = Rte_IRead_Run1ms_EngineSpeedIn_EngineSpeed();
    (void)EngineSpeed;  /* TODO: use value */

    uint8 ThrottlePosition = Rte_IRead_Run1ms_ThrottleIn_ThrottlePosition();
    (void)ThrottlePosition;  /* TODO: use value */

    uint16 EngineSpeedFwd = (uint16)0;  /* TODO: set value */
    Rte_IWrite_Run1ms_EngineSpeedOut_EngineSpeedFwd(EngineSpeedFwd);

    uint8 ThrottlePositionFwd = (uint8)0;  /* TODO: set value */
    Rte_IWrite_Run1ms_ThrottleOut_ThrottlePositionFwd(ThrottlePositionFwd);

}

/**
 * CanGateway_InitCanGateway — Init — called once at ECU startup
 */
void CanGateway_InitCanGateway(void)
{
    /* TODO: implement */
}
