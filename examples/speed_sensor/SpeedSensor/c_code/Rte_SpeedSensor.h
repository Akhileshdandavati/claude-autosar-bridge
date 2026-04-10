/**
 * @file  Rte_SpeedSensor.h
 * @brief RTE API for SpeedSensor
 * @swc   SpeedSensor
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#ifndef RTE_SPEEDSENSOR_H
#define RTE_SPEEDSENSOR_H

#include "Rte_Types.h"

/* Run10ms */
#define Rte_IRead_Run10ms_SpeedPort_VehicleSpeed() \
    (*(uint16*)Rte_Inst_SpeedSensor.SpeedPort->VehicleSpeed)

#endif /* RTE_SPEEDSENSOR_H */
