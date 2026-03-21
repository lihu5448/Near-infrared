 
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
    NVIC_InitStructure.NVIC_IRQChannelPriority = 0x04;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);
    TIM_ITConfig(TIM14,TIM_IT_Update,ENABLE);
    
    // 使用最大可能值来提高精度
    // 48MHz / 65535 ≈ 732Hz
    // 732Hz * 732 ≈ 536Hz (不正好是1秒)
    // 所以需要用精确计算
    
    // 精确计算：48MHz = 48,000,000
    // 需要 预分频器 * 自动重装值 = 48,000,000
    
    // 方案2.1: 使用整数因子
    #define TIM_PRESCALER    48000   // 48,000
    #define TIM_PERIOD       1000    // 1,000
    // 48,000 * 1,000 = 48,000,000 正好
    
    TIM_BaseInitStructure.TIM_Period = TIM_PERIOD - 1;
    TIM_BaseInitStructure.TIM_Prescaler = TIM_PRESCALER - 1;
    TIM_BaseInitStructure.TIM_ClockDivision = 0;
    TIM_BaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_BaseInitStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit(TIM14, &TIM_BaseInitStructure);
    
    TIM_Cmd(TIM14, ENABLE);
}

/**
  * @brief  定时器中断
  * @param  无
  * @retval 无
  */
// TIM14 中断服务函数 - 用于判断新的一圈数据

//允许adc读标志位
extern uint8_t read_ok_flag;

//测量计数 
extern int32_t measuring_count;
extern int32_t measuring_count_last;
void TIM14_IRQHandler(void)
{
  if(TIM_GetITStatus(TIM14, TIM_IT_Update) != RESET)
   {
      TIM_ClearITPendingBit(TIM14, TIM_IT_Update);  
		  if(measuring_count - measuring_count_last < 5) //1s内读取次数小于5  清楚标志位
			{
		    //清除计数和标志位
        measuring_count = 0;
				measuring_count_last = 0;				
		    read_ok_flag = 0;			
			}        
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



