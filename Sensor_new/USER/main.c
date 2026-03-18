#include "led.h"
#include "delay.h"
#include "key.h"
#include "sys.h"
#include "lcd.h"
#include "usart.h"	 
#include "adc.h"
#include "dac.h"
#include <stdio.h> 
 
/************************************************
 ALIENTEK精英STM32开发板实验17
 ADC 实验   
 技术支持：www.openedv.com
 淘宝店铺：http://eboard.taobao.com 
 关注微信公众平台微信号："正点原子"，免费获取STM32资料。
 广州市星翼电子科技有限公司  
 作者：正点原子 @ALIENTEK
************************************************/

char flag = 1; 

int main(void)
{	 
    unsigned char ad_get[5];
    u16 adcx;
    float temp;
	u8 t = 0;	 
	u16 dacval = 0;
	u8 key;
	u8 auto_mode = 1;	// 自动模式标志位，1表示自动缓慢上升
	u16 target_dacval;	// 目标DAC值
	u8 rising = 1;		// 上升标志位
   
	// 计算1.6V对应的DAC值 (12位分辨率，参考电压3.3V)
	// 公式：DAC值 = (目标电压 / 参考电压) * (2^12 - 1)
	target_dacval = (u16)((1.64 / 3.3) * 4095);
    
    ad_get[0] = 0x5A;
    ad_get[1] = 0xA5;    
    
    delay_init();	      // 延时函数初始化	  
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2); // 设置中断优先级分组为组2：2位抢占优先级，2位响应优先级
    uart_init(115200);	  // 串口初始化为115200
    LED_Init();			  // LED端口初始化
    LCD_Init();			 	
    Adc_Init();		      // ADC初始化
	Dac1_Init();				//DAC初始化
    
	POINT_COLOR = RED; //设置字体为红色 
	LCD_ShowString(60, 50, 200, 16, 16, "Elite STM32");	
	LCD_ShowString(60, 70, 200, 16, 16, "DAC TEST");	
	LCD_ShowString(60, 90, 200, 16, 16, "ATOM@ALIENTEK");
	LCD_ShowString(60, 110, 200, 16, 16, "2024/1/7");	
	LCD_ShowString(60, 130, 200, 16, 16, "WK_UP:Mode KEY1:Stop/Start");	
	LCD_ShowString(60, 145, 200, 16, 16, "Target:1.6V");	
	//显示提示信息											      
	POINT_COLOR = BLUE; //设置字体为蓝色
	LCD_ShowString(60, 165, 200, 16, 16, "DAC VAL:");	      
	LCD_ShowString(60, 185, 200, 16, 16, "DAC VOL:0.000V");	      
	LCD_ShowString(60, 205, 200, 16, 16, "ADC VOL:0.000V");
	LCD_ShowString(60, 225, 200, 16, 16, "MODE: AUTO");       
    
    printf("ADC Voltage Measurement Start...\r\n");  // 串口发送启动信息
	DAC_SetChannel1Data(DAC_Align_12b_R, 0); //初始值为0
    
    while(1)
    {
t++;
key = KEY_Scan(0);			  

// 自动模式下WK_UP按键用于暂停/继续
if(key == WKUP_PRES)
{
	rising = !rising;
	if(rising)
		LCD_ShowString(60, 225, 200, 16, 16, "MODE: AUTO   ");
	else
		LCD_ShowString(60, 225, 200, 16, 16, "MODE: PAUSE  ");
}

// 自动模式：缓慢上升到1.6V
if(rising)
{
	if(t % 5 == 0) // 每50ms增加一次（10ms*5）
	{
		if(dacval < target_dacval)
		{
			// 缓慢上升，每次增加10个LSB
			if(target_dacval - dacval > 10)
				dacval += 10;
			else
				dacval = target_dacval; // 达到目标值
			
			DAC_SetChannel1Data(DAC_Align_12b_R, dacval); //设置DAC值
		}
		else if(dacval >= target_dacval)
		{
			// 达到目标值后保持
			dacval = target_dacval;
			DAC_SetChannel1Data(DAC_Align_12b_R, dacval); //设置DAC值
		}
	}
}

// 每100ms或按键按下时更新显示
if(t == 10 || key == WKUP_PRES)
{	  
	adcx = DAC_GetDataOutputValue(DAC_Channel_1); //读取前面设置DAC的值
	LCD_ShowxNum(124, 165, adcx, 4, 16, 0);     	//显示DAC寄存器值
	
	temp = (float)adcx * (3.3 / 4096); //得到DAC电压值
	adcx = temp;
	LCD_ShowxNum(124, 185, temp, 1, 16, 0);     	//显示电压值整数部分
	temp -= adcx;
	temp *= 1000;
	LCD_ShowxNum(140, 185, temp, 3, 16, 0X80); 	//显示电压值的小数部分
	LED0 = !LED0;  // LED闪烁指示系统运行
	adcx = Get_Adc_Average(ADC_Channel_1, 10);	//得到ADC转换值	  
	temp = (float)adcx * (3.3 / 4096);			//得到ADC电压值
	adcx = temp;
          
    ad_get[2] = ((int)(temp*1000));
    ad_get[3] = ((int)(temp*1000)) >>8 ;
    
    ad_get[4] =  0xAB;
    
    USART1_SendArray(ad_get,5);
    
	LCD_ShowxNum(124, 205, temp, 1, 16, 0);     	//显示电压值整数部分
	temp -= adcx;
	temp *= 1000;
	LCD_ShowxNum(140, 205, temp, 3, 16, 0X80); 	//显示电压值的小数部分
	
	LED0 = !LED0;	   
	t = 0;
   }	
   delay_ms(10);
//        t++;
//		key = KEY_Scan(0);			  
//		
//		// WK_UP按键切换自动/手动模式
//		if(key == WKUP_PRES)
//		{		 
//			auto_mode = !auto_mode;
//			if(auto_mode)
//				LCD_ShowString(60, 225, 200, 16, 16, "MODE: AUTO   ");
//			else
//				LCD_ShowString(60, 225, 200, 16, 16, "MODE: MANUAL ");
//		}
//		// KEY1按键在手动模式下控制DAC值
//		else if(key == KEY1_PRES)	
//		{
//			if(!auto_mode) // 手动模式
//			{
//				if(dacval > 200)
//					dacval -= 200;
//				else
//					dacval = 0;
//				DAC_SetChannel1Data(DAC_Align_12b_R, dacval); //设置DAC值
//			}
//			else // 自动模式下KEY1用于暂停/继续
//			{
//				rising = !rising;
//				if(rising)
//					LCD_ShowString(60, 225, 200, 16, 16, "MODE: AUTO   ");
//				else
//					LCD_ShowString(60, 225, 200, 16, 16, "MODE: PAUSE  ");
//			}
//		}
//		
//		// 自动模式：缓慢上升到1.6V
//		if(auto_mode && rising)
//		{
//			if(t % 5 == 0) // 每50ms增加一次（10ms*5）
//			{
//				if(dacval < target_dacval)
//				{
//					// 缓慢上升，每次增加10个LSB
//					if(target_dacval - dacval > 10)
//						dacval += 10;
//					else
//						dacval = target_dacval; // 达到目标值
//					
//					DAC_SetChannel1Data(DAC_Align_12b_R, dacval); //设置DAC值
//				}
//				else if(dacval >= target_dacval)
//				{
//					// 达到目标值后保持
//					dacval = target_dacval;
//					DAC_SetChannel1Data(DAC_Align_12b_R, dacval); //设置DAC值
//				}
//			}
//		}
//		
//		// 每100ms或按键按下时更新显示
//		if(t == 10 || key == KEY1_PRES || key == WKUP_PRES)
//		{	  
//			adcx = DAC_GetDataOutputValue(DAC_Channel_1); //读取前面设置DAC的值
//			LCD_ShowxNum(124, 165, adcx, 4, 16, 0);     	//显示DAC寄存器值
//			
//			temp = (float)adcx * (3.3 / 4096); //得到DAC电压值
//			adcx = temp;
//			LCD_ShowxNum(124, 185, temp, 1, 16, 0);     	//显示电压值整数部分
//			temp -= adcx;
//			temp *= 1000;
//			LCD_ShowxNum(140, 185, temp, 3, 16, 0X80); 	//显示电压值的小数部分
//			LED0 = !LED0;  // LED闪烁指示系统运行
//			adcx = Get_Adc_Average(ADC_Channel_1, 10);	//得到ADC转换值	  
//			temp = (float)adcx * (3.3 / 4096);			//得到ADC电压值
//			adcx = temp;
//                  
//            ad_get[2] = ((int)(temp*1000));
//            ad_get[3] = ((int)(temp*1000)) >>8 ;
//        
//            ad_get[4] =  0xAB;
//        
//            USART1_SendArray(ad_get,5);
//            
//			LCD_ShowxNum(124, 205, temp, 1, 16, 0);     	//显示电压值整数部分
//			temp -= adcx;
//			temp *= 1000;
//			LCD_ShowxNum(140, 205, temp, 3, 16, 0X80); 	//显示电压值的小数部分
//			
//			LED0 = !LED0;	   
//			t = 0;
//		}	
//    	delay_ms(10);    
	}
 }

