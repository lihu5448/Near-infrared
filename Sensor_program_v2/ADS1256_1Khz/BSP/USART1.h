#ifndef __BSP_USART1_H
#define __BSP_USART1_H

#include "stm32f0xx.h"
#include <stdio.h>

#ifdef __GNUC__
  /* With GCC/RAISONANCE, small printf (option LD Linker->Libraries->Small printf
     set to 'Yes') calls __io_putchar() */
  #define PUTCHAR_PROTOTYPE int __io_putchar(int ch)
#else
  #define PUTCHAR_PROTOTYPE int fputc(int ch, FILE *f)
#endif /* __GNUC__ */

/*******************************************************************************/
extern uint32_t UART1_FifoNaber;
extern volatile uint8_t  UART1_STATE;
void USART1_Init(uint32_t BaudRate);
uint8_t USART1_DmaSendBuf(uint8_t *buf,uint32_t len);
void USART1_SendBuf(uint8_t *buf,uint32_t len) ;
/*******************************************************************************/	
#endif
