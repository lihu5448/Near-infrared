 
#include "TIM.h"

//=============================================================================
//文件名称：Delay
//功能概要：延时函数
//参数说明：无
//函数返回：无
//=============================================================================
void delay_ms(uint32_t nCount)
{
	uint32_t n;
	
	while(nCount--)
	{
		for(n=0x2FFF; n != 0; n--);
	}
}
/****************************************
延时uS  
*****************************************/
void delay_us(uint32_t nCount)						  
{
	uint32_t i=0;
	while(nCount--)
	{
		i=1;
		while(i--);
  }
}
 

#define OVERFLOW_PERIOD	  65000U
#define FRQ_DIVE					12

volatile uint32_t overflow_flag =0,last_cnt,now;
float frq;

/**
  * @brief  初始化定时器
  * @param  无
  * @retval 无
  */
void tim_start(void)
{
	TIM_TimeBaseInitTypeDef TIM_BaseInitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM14, ENABLE);  

	TIM_ClearFlag(TIM14,TIM_IT_Update);
	NVIC_InitStructure.NVIC_IRQChannel = TIM14_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x00;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
	TIM_ITConfig(TIM14,TIM_IT_Update,ENABLE);//使能接收中断
	
	frq = 48000000/FRQ_DIVE;	
	TIM_BaseInitStructure.TIM_Period = OVERFLOW_PERIOD-1;
	TIM_BaseInitStructure.TIM_Prescaler = (FRQ_DIVE-1);
	TIM_BaseInitStructure.TIM_ClockDivision = 0;
	TIM_BaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
	TIM_BaseInitStructure.TIM_RepetitionCounter = 0;
	TIM_TimeBaseInit(TIM14, &TIM_BaseInitStructure);
	TIM_Cmd(TIM14, ENABLE);
	last_cnt = TIM_GetCounter(TIM14);
}

/**
  * @brief  定时器中断
  * @param  无
  * @retval 无
  */
void TIM14_IRQHandler(void)
{
	if(TIM_GetITStatus(TIM14,TIM_IT_Update) != RESET)
	{
			TIM_ClearITPendingBit(TIM14,TIM_IT_Update); 
			overflow_flag++;
	}
}

/**
  * @brief  读取时间
  * @param  无
  * @retval 无
  */
float get_dt(void)
{
	// the interval between call get_dt_us should not been more than 16ms;
	now = TIM_GetCounter(TIM14);
	float dt = ((now < last_cnt)?(now+OVERFLOW_PERIOD-last_cnt):(now-last_cnt))/frq;
	last_cnt = now;	
	return dt; 
}


/**********************************************************************************************
**********************************************************************************************
**********************************************************************************************/

__IO uint32_t SysTimMs=0;


/**
  * @brief  初始化SYS定时器
  */
void systim_start(void)
{
	TIM_TimeBaseInitTypeDef TIM_BaseInitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3, ENABLE);  

	TIM_ClearFlag(TIM3,TIM_IT_Update);
	NVIC_InitStructure.NVIC_IRQChannel = TIM3_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x00;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
	TIM_ITConfig(TIM3,TIM_IT_Update,ENABLE);//使能接收中断
	
	TIM_BaseInitStructure.TIM_Period = 1000-1;
	TIM_BaseInitStructure.TIM_Prescaler = (48-1);
	TIM_BaseInitStructure.TIM_ClockDivision = 0;
	TIM_BaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
	TIM_BaseInitStructure.TIM_RepetitionCounter = 0;
	TIM_TimeBaseInit(TIM3, &TIM_BaseInitStructure);
	TIM_Cmd(TIM3, ENABLE);
}

/**
  * @brief  定时器中断
  * @param  无
  * @retval 无
  */
void TIM3_IRQHandler(void)
{
	if(TIM_GetITStatus(TIM3,TIM_IT_Update) != RESET)
	{
			TIM_ClearITPendingBit(TIM3,TIM_IT_Update); 
			SysTimMs++;
	}
}

uint32_t HAL_GetTick(void)
{
  return SysTimMs;
}



