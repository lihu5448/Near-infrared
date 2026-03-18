/*
*********************************************************************************************************
*
*	模块名称 : LED指示灯驱动模块
*	文件名称 : bsp_led.c
*	版    本 : V1.0
*	说    明 : 驱动LED指示灯
*
*	修改记录 :
*		版本号  日期        作者     说明
*		V1.0    2015-10-11 armfly  正式发布
*
*	Copyright (C), 2015-2016, 安富莱电子 www.armfly.com
*
*********************************************************************************************************
*/

#include "bsp.h"

/*
*********************************************************************************************************
*	函 数 名: bsp_InitLed
*	功能说明: 配置LED指示灯相关的GPIO,  该函数被 bsp_Init() 调用。
*	形    参:  无
*	返 回 值: 无
*********************************************************************************************************
*/

void LED_Init(void)
{    	 
  GPIO_InitTypeDef  GPIO_InitStructure;

  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA |RCC_AHB1Periph_GPIOD, ENABLE);//使能GPIOA时钟

  //GPIOA6、A7   开发板指示灯
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_6 | GPIO_Pin_7;//LED0和LED1对应IO口
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;//普通输出模式
  GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
  GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化GPIO
	
  GPIO_SetBits(GPIOA,GPIO_Pin_6 | GPIO_Pin_7);//设置高，灯灭
	
  //GPIOD8、D10   近红外电流源使能脚
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_8 | GPIO_Pin_10;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;//普通输出模式
  GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
  GPIO_Init(GPIOD, &GPIO_InitStructure);//初始化GPIO
	
  GPIO_ResetBits(GPIOD,GPIO_Pin_8 | GPIO_Pin_10);//设置高， 电流源不输出

}

void bsp_InitLed(void)
{
    LED_Init();
	bsp_LedOff(1);
	bsp_LedOff(2);
}

/*
*********************************************************************************************************
*	函 数 名: bsp_LedOn
*	功能说明: 点亮指定的LED指示灯。
*	形    参:  _no : 指示灯序号，范围 1 - 4
*	返 回 值: 无
*********************************************************************************************************
*/
void bsp_LedOn(uint8_t _no)
{
	if (_no == 1)
	{
		GPIO_ResetBits(GPIOA,GPIO_Pin_6 );
	}
	else if (_no == 2)
	{
		GPIO_ResetBits(GPIOA,GPIO_Pin_7 );
	}
}

/*
*********************************************************************************************************
*	函 数 名: bsp_LedOff
*	功能说明: 熄灭指定的LED指示灯。
*	形    参:  _no : 指示灯序号，范围 1 - 4
*	返 回 值: 无
*********************************************************************************************************
*/
void bsp_LedOff(uint8_t _no)
{
	if (_no == 1)
	{
        GPIO_SetBits(GPIOA,GPIO_Pin_6);
	}
	else if (_no == 2)
	{
        GPIO_SetBits(GPIOA,GPIO_Pin_7);
	}
}

/*
*********************************************************************************************************
*	函 数 名: bsp_LedToggle
*	功能说明: 翻转指定的LED指示灯。
*	形    参:  _no : 指示灯序号，范围 1 - 4
*	返 回 值: 按键代码
*********************************************************************************************************
*/
void bsp_LedToggle(uint8_t _no)
{
//	uint32_t pin;
//	
//	if (_no == 1)
//	{
//		pin = LED1;
//	}
//	else if (_no == 2)
//	{
//		pin = LED2;
//	}
//	else if (_no == 3)
//	{
//		pin = LED3;
//	}
//	else if (_no == 4)
//	{
//		pin = LED4;
//	}
//	else
//	{
//		return;
//	}

//	if (HC574_GetPin(pin))
//	{
//		HC574_SetPin(pin, 0);
//	}
//	else
//	{
//		HC574_SetPin(pin, 1);
//	}	
}

///*
//*********************************************************************************************************
//*	函 数 名: bsp_IsLedOn
//*	功能说明: 判断LED指示灯是否已经点亮。
//*	形    参:  _no : 指示灯序号，范围 1 - 4
//*	返 回 值: 1表示已经点亮，0表示未点亮
//*********************************************************************************************************
//*/
//uint8_t bsp_IsLedOn(uint8_t _no)
//{
////	uint32_t pin;
////	
////	if (_no == 1)
////	{
////		pin = LED1;
////	}
////	else if (_no == 2)
////	{
////		pin = LED2;
////	}
////	else if (_no == 3)
////	{
////		pin = LED3;
////	}
////	else if (_no == 4)
////	{
////		pin = LED4;
////	}
////	else
////	{
////		return 0;
////	}
////	
////	if (HC574_GetPin(pin))
////	{
////		return 0;	/* 灭 */
////	}
////	else
////	{
////		return 1;	/* 亮 */
////	}
//}






