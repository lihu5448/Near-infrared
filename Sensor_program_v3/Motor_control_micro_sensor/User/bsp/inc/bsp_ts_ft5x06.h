/*
*********************************************************************************************************
*
*	模块名称 : ft5x06电容触摸芯片驱动程序
*	文件名称 : bsp_ts_ft5x06.h
*	说    明 : 头文件
*	版    本 : V1.0
*
*	Copyright (C), 2015-2020, 安富莱电子 www.armfly.com
*********************************************************************************************************
*/

#ifndef _BSP_TS_FT5X06_H
#define _BSP_TS_FT5X06_H

/* I2C总线，器件ID */
#define FT5X06_I2C_ADDR       0x70

#define FT5X06_TOUCH_POINTS   5		/* 支持的触摸点数 */

/* 寄存器地址 */
#define FT5X06_REG_FW_VER     0xA6		/* 固件版本 */
#define FT5X06_REG_POINT_RATE 0x88		/* 速率 */
#define FT5X06_REG_THGROUP    0x80		/* 门槛 */

#define CFG_POINT_READ_BUF  (3 + 6 * (FT5X06_TOUCH_POINTS))    // 33字节

typedef struct
{
	uint8_t Enable;
	uint8_t TimerCount;
	
	uint8_t Count;		/* 几个点按下 */
	
	uint16_t X[FT5X06_TOUCH_POINTS];
	uint16_t Y[FT5X06_TOUCH_POINTS];	
	uint8_t id[FT5X06_TOUCH_POINTS];
	uint8_t Event[FT5X06_TOUCH_POINTS];
}FT5X06_T;

void FT5X06_InitHard(void);
uint8_t FT5X06_PenInt(void);
uint16_t FT5X06_ReadVersion(void);
void FT5X06_Scan(void);
void FT5X06_Timer1ms(void);

extern FT5X06_T g_tFT5X06;

#endif

/***************************** 安富莱电子 www.armfly.com (END OF FILE) *********************************/
