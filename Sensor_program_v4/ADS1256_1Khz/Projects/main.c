//=============================================================================
//功能概要：STM32F030F4 ADS1256测试
//版本更新：2024-11-13
//调试平台：MDK Keil V5.32
//运行硬件平台：ADS1256评估模块 V1.1
//联系方式：QQ492841230 
//=============================================================================

//头文件
#include "stm32f0xx.h"
#include "USART1.h"
#include "my_fifo.h"
#include "TIM.h"
#include "my_flash.h"
#include "ADS1255.h"


double  VolF;
int32_t Vol[360];

/*协议说明*/
//0，1 -》  0x5A,0xA5       协议头
//2    -》  0x00 啥也不是  0x01  代表测量光  0x02  代表参考光
//3-6  -》  电压值*1000000   小端存放
//7    -》  (SendBuf[3] + SendBuf[4] +SendBuf[5] +SendBuf[6])& 0xff;   //只保留和的 低八位
//8-9  -》  0x0D,0x0A       协议尾

uint8_t SendBuf[10] = {0x5A,0xA5,0x00,0x00,0x00,0x00,0x00,0x00,0x0D,0x0A};  //用作串口输出缓存

//允许adc读标志位
uint8_t read_ok_flag = 0;

//测量计数 
int32_t measuring_count = 0;
int32_t measuring_count_last = 0;

/*******************************************************************************
对固定通道进行连续采样测试
*******************************************************************************/
void ADC_SendData(double Vol)
{

	int32_t V=(int32_t)(Vol*1000000);
//	SendBuf[0] =0x5A;
//	SendBuf[1] =0xA5;
	// SendBuf[2] =0x00;     // 0x01  代表测量光     0x02  代表参考光
	SendBuf[3] =(uint8_t)V;
	SendBuf[4] =(uint8_t)(V>>8);
	SendBuf[5] =(uint8_t)(V>>16);
	SendBuf[6] =(uint8_t)(V>>24);
	SendBuf[7] =(SendBuf[3] + SendBuf[4] +SendBuf[5] +SendBuf[6])& 0xff;   //只保留和的 低八位
//	SendBuf[8] = 0x0D;  // 回车的ASCII码
//	SendBuf[9] = 0x0A;  // 换行的ASCII码
	
	USART1_DmaSendBuf(SendBuf,10);
}

/*******************************************************************************
对固定通道进行连续采样测试
*******************************************************************************/

void Measure_GPIO_EXTI_Config(void) 
{
	
	GPIO_InitTypeDef GPIO_InitStructure;
  EXTI_InitTypeDef EXTI_InitStructure;
  NVIC_InitTypeDef NVIC_InitStructure;
 
	
	// 使能 SYSCFG 时钟
	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_GPIOA,ENABLE);
	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_GPIOF,ENABLE);
	
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_SYSCFG, ENABLE);

  //两控制电流源的引脚
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_Level_3;        
  GPIO_Init(GPIOF,&GPIO_InitStructure);   
	
	GPIO_SetBits(GPIOF ,GPIO_Pin_0);	
	GPIO_SetBits(GPIOF ,GPIO_Pin_1);	
	
	//两外部中断引脚
	//  PA1    测量、参考
	//  PA2    脉冲触发
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_1 | GPIO_Pin_2;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_Level_3;        
  GPIO_Init(GPIOA,&GPIO_InitStructure);  

	// 配置 EXTI 线与 GPIO 映射
	SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOA, EXTI_PinSource1);
	SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOA, EXTI_PinSource2);

	EXTI_InitStructure.EXTI_Line = EXTI_Line1;
	EXTI_InitStructure.EXTI_Mode = EXTI_Mode_Interrupt;
	EXTI_InitStructure.EXTI_Trigger = EXTI_Trigger_Rising_Falling;
	EXTI_InitStructure.EXTI_LineCmd = ENABLE;
	EXTI_Init(&EXTI_InitStructure);

	EXTI_InitStructure.EXTI_Line = EXTI_Line2;
	EXTI_InitStructure.EXTI_Mode = EXTI_Mode_Interrupt;
	EXTI_InitStructure.EXTI_Trigger = EXTI_Trigger_Rising;
	EXTI_InitStructure.EXTI_LineCmd = ENABLE;
	EXTI_Init(&EXTI_InitStructure);
	
	NVIC_InitStructure.NVIC_IRQChannel = EXTI0_1_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x02;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	NVIC_InitStructure.NVIC_IRQChannel = EXTI2_3_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x01;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
}




// 测量光参考光的区分
// PA1高电平   测量光
// PA1低电平   参考光  
void EXTI0_1_IRQHandler(void)
{   
   if((EXTI->PR & (1<<1)) != (uint32_t)RESET )
   {  
		if(GPIOA->IDR & (1<<1)) //高电平
		  {
			   GPIOF -> ODR  &= ~(1<<0);    //PF0拉低 -》测量LED 电流源使能
         GPIOF -> ODR  |=  1<<1;      //PF1拉高 -》参考LED 电流源失能						
				 SendBuf[2] =0x01;  //  0x01代表测量光
		  }
		else                     //低电平
		 {
			 	if((GPIOA->IDR & (1<<1)) == 0)
		    {
					GPIOF -> ODR  |=  1<<0;       //PF0拉高 -》测量灯 电流源失能
			    GPIOF -> ODR  &= ~(1<<1);     //PF1拉低 -》参考灯 电流源使能								
				  SendBuf[2] =0x02;  //  0x00   啥也不是
				}
		 } 
    EXTI->PR  = 1<<1;//清除中断标志位
   }
}


//  脉冲触发ADC采集
void EXTI2_3_IRQHandler(void)
{   
   if(( EXTI->PR & (1<<2)) != (uint32_t)RESET )
   {     	 
		 if(GPIOA->IDR & (1<<2)) 
		 {	
       if(ADS1255_DRDY()==0)
		    {	     			
				  Vol[measuring_count] = ADS1255_ContinuousRead_AdcData(); 
				}	
				
			 if(measuring_count == 359)
				{
  			 read_ok_flag = 1;	
			  }	
				measuring_count_last = measuring_count;
				measuring_count++;
        printf("%d  %d\r\n",measuring_count,read_ok_flag);				
		  }        	 		 
		 EXTI->PR = 1<<2 ;  
   }
}

//=============================================================================
//文件名称：main
//功能概要：主函数
//参数说明：无
//函数返回：int
//=============================================================================

uint8_t test = 0;

int main(void)
{	
	int16_t i;
	delay_ms(3000);//等待电机、主控板稳定	
	
	Measure_GPIO_EXTI_Config();		
	
  USART1_Init(115200);//USART1初始化	
	
	tim_start();  //定时器14 用于判断  1s内读取次数小于5，清楚标志位
	
	ADC_ConfigTypeDef ADCConfig;//ADC配置结构体	
	
	ADS1255_IO_Init();//IO初始化 
	ADCConfig.AIN_P=AdcAin_AIN0;//输入AIN
	ADCConfig.AIN_N=AdcAin_AIN1;//输入AIN	
	ADCConfig.AinBuf=AdcInBuf_ON;//打开输入缓冲
	ADCConfig.ClockOut=AdcClockOut_OFF;//7.68M时钟输出关闭
	ADCConfig.PGA=AdcPga_GAN1;//PGA放大倍数1
	ADCConfig.SenserTestCurrent=AdcTestCurrent_OFF;//关闭测试电流
	ADCConfig.SPS=AdcSpeed_1000SPS;//ADC采样率1000sps
	ADCConfig.ADC_RefVol=2.5;//ADC参考源电压
	if(ADS1255_config(ADCConfig)!=0)//ADC寄存器配置
	{
		printf("ADS1256init fail  Reset\r\n");
		delay_ms(100);
		NVIC_SystemReset();
	}
	else
	{
	  printf("ADS1256init sucessful\r\n");
	}
	
	
	ADS1255_WAKEUP();//唤醒单片机
	while(ADS1255_DRDY()!=0){};//等待ADC准备好
	ADS1255_AdjSELF();//对ADC进行一次内部校准
	while(ADS1255_DRDY()!=0){};//等待ADC准备好
	ADS1255_SYNC();   //AD转换同步
	ADS1255_WAKEUP(); //启动同步
	while(ADS1255_DRDY()!=0){};//等待ADC准备好	
		
	ADS1255_RDATAC();//发送连续读取ADC指令
	delay_us(15);//等待最少50个ADC时钟周期
		
	while(1)
	{	 
    if(read_ok_flag == 1)  //读完360个数据  统一通过串口发送给上位机
		{ 
			for(i=0;i<360;i++)
			{
			  VolF=ADS1255_DataFormatting(Vol[i],ADCConfig.ADC_RefVol,0x01<<ADCConfig.PGA);//把ADC转换为电压值
		  	ADC_SendData(VolF);//串口发送电压
			}	
			measuring_count = 0;
			measuring_count_last = 0;	
			
			read_ok_flag = 0;		
      printf("send  ok \r\n");					
		}						
	}		
}


/*****END OF FILE****/
