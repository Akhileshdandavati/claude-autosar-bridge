/**
 * @file  SpeedSensor.c
 * @brief Runnable implementations for SpeedSensor
 * @swc   SpeedSensor
 * @gen   claude-autosar-bridge
 * @date  2026-04-09 23:52:38
 * AUTO-GENERATED - DO NOT EDIT
 */

#include "SpeedSensor.h"

/**
 * SpeedSensor_Run10ms — Periodic — every 10ms
 * reads SpeedPort.VehicleSpeed (uint16)
 */
void SpeedSensor_Run10ms(void)
{
    uint16 VehicleSpeed = Rte_IRead_Run10ms_SpeedPort_VehicleSpeed();
    (void)VehicleSpeed;  /* TODO: use value */

}

/**
 * SpeedSensor_InitSpeedSensor — Init — called once at ECU startup
 */
void SpeedSensor_InitSpeedSensor(void)
{
    /* TODO: implement */
}
