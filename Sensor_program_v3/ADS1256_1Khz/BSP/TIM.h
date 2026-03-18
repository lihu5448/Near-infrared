#ifndef __TIM_H
#define	__TIM_H

#include "stm32f0xx.h"
void tim_start(void);
float get_dt(void);
uint32_t HAL_GetTick(void);
void systim_start(void);
void delay_ms(uint32_t nCount);
void delay_us(uint32_t nCount);
#endif
