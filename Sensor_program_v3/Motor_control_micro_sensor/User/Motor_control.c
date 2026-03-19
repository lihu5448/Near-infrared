/*
*********************************************************************************************************
*	                                  
*	模块名称 : MS4005步进电机控制
*	文件名称 : motor_control;.c
*
*********************************************************************************************************
*/
#include "includes.h"
#include "Motor_data_process.h"


extern QueueHandle_t xQueue1;
extern QueueHandle_t xQueue2;
extern EventGroupHandle_t Motor_rotate_event;
extern  TimerHandle_t xTimers;

extern  u8  timer_count;
extern  MS_Motor_Params_t  MS4005;


uint32_t Motor_Id = 0x141;
u16 MaxSpeed = 600;
uint8_t key_press = 0;


//PC5 上升沿触发
void  motor_gpio_init()
{
  GPIO_InitTypeDef  GPIO_InitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;// 设置中断优先级结构体变量
	EXTI_InitTypeDef EXTI_InitStructure;//设置外部中断结构体结构体变量
	
  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC, ENABLE);//使能GPIOE时钟
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_SYSCFG,ENABLE); //使能SYSCFG时钟


  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_5;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
  GPIO_InitStructure.GPIO_OType = GPIO_OType_OD;
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_DOWN;//
  GPIO_Init(GPIOC, &GPIO_InitStructure);//初始化GPIO	
	
	SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC,EXTI_PinSource5); //PA0连接中断线0，映射按键KEY_UP   简单来说 接下来四条语句实现把引脚接在对应的中断线上，类似于复用功能
 
	EXTI_InitStructure.EXTI_Line=EXTI_Line5;//
	EXTI_InitStructure.EXTI_LineCmd=ENABLE;//
	EXTI_InitStructure.EXTI_Mode=EXTI_Mode_Interrupt;//
	EXTI_InitStructure.EXTI_Trigger=EXTI_Trigger_Rising;//
	EXTI_Init(&EXTI_InitStructure);//初始化外部中断
		
	NVIC_InitStructure.NVIC_IRQChannel=EXTI9_5_IRQn;//
	NVIC_InitStructure.NVIC_IRQChannelCmd=ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=0x02;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority=0x00;
	NVIC_Init(&NVIC_InitStructure);

}


void EXTI9_5_IRQHandler(void) 
{ 
//	BaseType_t xResult;
//	BaseType_t xHigherPriorityTaskWoken = pdFALSE;
//	
//  if(EXTI_GetITStatus(EXTI_Line5)!=RESET)     
//  { 
//	  if(key_press == 1)  // 测量旋转
//		{
//		/* 向任务vTaskMsgPro发送事件标志 */
//		xResult = xEventGroupSetBitsFromISR(Motor_rotate_event, /* 事件标志组句柄 */
//									    BIT_0 ,             /* 设置bit0 */
//									    &xHigherPriorityTaskWoken );

//		}
//		else if(key_press == 2)	 //参考旋转
//		{
//			/* 向任务vTaskMsgPro发送事件标志 */
//			xResult = xEventGroupSetBitsFromISR(Motor_rotate_event, /* 事件标志组句柄 */
//									    BIT_1 ,             /* 设置bit1 */
//									    &xHigherPriorityTaskWoken );   
//		}
//		
//	   /* 消息被成功发出 */
//   	 if( xResult != pdFAIL )
//				{
//				  portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
//				}
//		
    EXTI_ClearITPendingBit(EXTI_Line5);   		
//  }    
} 



void Motor_Init(void)
{
	 uint16_t  target_encoder =  0;
	 int32_t target_angle ;
	 
	 delay_ms(2000);  //让电机初始化完成
	
	 Motor_operation(Motor_Id); 
	
	 delay_ms(100);
	 
//	 target_angle = (int32_t)(target_encoder)*100 * 360 / 32768;
//	 Multiloop_position_closedloop_control1(Motor_Id , target_angle);
	
   Multiloop_position_closedloop_control1(Motor_Id , 0);	
	
	 MS4005.angle_last = 0;
	 MS4005.angle_error = 0;
	 MS4005.motor_rotate_count = 0; //初始旋转计数
	 motor_gpio_init();
	 
	 delay_ms(500);
}

/*
*********************************************************************************************************
*	函 数 名: Motor_control
*	功能说明: 电机控制函数
*	形    参: 无
*	返 回 值:
*********************************************************************************************************
*/

uint8_t key_test = 0;
uint8_t loop_finish = 0;


uint8_t ask_count = 0;

//  PD8    LED标志位
//  PD10   脉冲值，旋转完成之后会输出一个  高电平脉冲  

void Motor_control(void)
{	
	EventBits_t uxBits;	
	uint8_t ucKeyCode;	   	/* 按键代码 */
	
	while(1)
	{	
		  /* 处理按键事件 */
		  ucKeyCode = bsp_GetKey();	
	   	if (ucKeyCode > 0)
		   {
				/* 有键按下 */
			 switch (ucKeyCode)
				{
	 			 case KEY_DOWN_K0:			  /* K0键    测量灯亮  开始测量 */
				 if (key_press == 0) {
					key_press = 1;
					GPIO_SetBits(GPIOD,GPIO_Pin_8);  // 测量灯亮	 
				  vTaskDelay(pdMS_TO_TICKS(500));  //等待led电流源稳定
				 }
					break; 

				case KEY_DOWN_K1:			  /* K1键    参考灯正转一圈*/
					if (key_press == 0) {
					key_press = 2;
				  GPIO_ResetBits(GPIOD,GPIO_Pin_8);    // 参考灯亮
					vTaskDelay(pdMS_TO_TICKS(500)); //给电流源稳定的时间
					}
					break;

				case KEY_DOWN_WKUP:			/* 电机停止 */
					//Read_the_motor_status1(Motor_Id);
					 Read_encoder_data(Motor_Id);
					break;
				
				default:
					/* 其它的键值不处理 */
					break;
				}			
			}

	  if (key_test > 0)
			{
//			/* 有键按下 */
			 switch (key_test)
			  {
	 			 case 1:			  /* K0键    测量灯亮  开始测量 */
				 if (key_press == 0) {
					key_press = 1;
					GPIO_SetBits(GPIOD,GPIO_Pin_8);  // 测量灯亮	 
	        Multiloop_position_closedloop_control1(Motor_Id ,0);	//位置归零		
          MS4005.motor_rotate_count = 0;					 
				  vTaskDelay(pdMS_TO_TICKS(500));  //等待led电流源稳定
					Incremental_position_closed_loop2( Motor_Id,MaxSpeed,100);	 //顺时针旋转1度
				  xTimerStart(xTimers, 0) ;
							
				 }
					break; 

				case 2:			  /* K1键    参考灯正转一圈*/
					if (key_press == 0) {
					key_press = 2;
				  GPIO_ResetBits(GPIOD,GPIO_Pin_8);    // 参考灯亮
	        Multiloop_position_closedloop_control1(Motor_Id ,0);
					MS4005.motor_rotate_count = 0;
					vTaskDelay(pdMS_TO_TICKS(500)); //给电流源稳定的时间
					Incremental_position_closed_loop2( Motor_Id,MaxSpeed,100);	 //顺时针旋转1度		
				  xTimerStart(xTimers, 0);						

					}
					break;

				case 3:		
					 Read_encoder_data(Motor_Id);
					break;
				
				default:
					/* 其它的键值不处理 */
					break;
				}
			  key_test = 0;
			}
			
			
//按键处理代码   
		if(key_press != 0)
		{
		/* 上升沿中断     */
		uxBits = xEventGroupWaitBits(Motor_rotate_event,
							         BIT_0 | BIT_1,        // 等待两个事件位    
							         pdTRUE,  						 // 清除事件位
							         pdFALSE,              // 不等待所有位
							         0); 	                 // 不等待										
			
		if((uxBits & BIT_0)== BIT_0 )  // 1度旋转完成
			{
				//脉冲  
	   	  GPIO_SetBits(GPIOD,GPIO_Pin_10);
				vTaskDelay(1);  //1us脉冲
		    GPIO_ResetBits(GPIOD,GPIO_Pin_10);
				
        MS4005.motor_rotate_count++;
				printf("motor_rotate_count: %d   angle_now:  %.2f   motor_encoder: %d \r\n",MS4005.motor_rotate_count, MS4005.angle_now, MS4005.encoder);
        if(MS4005.motor_rotate_count < 360)
				 {
					Incremental_position_closed_loop2( Motor_Id,MaxSpeed,100);	 //顺时针旋转1度		
				 }	
        else	
				{
				 MS4005.motor_rotate_count = 0;
				 
					xTimerStop(xTimers, 0) ;
					key_press = 0;
				}					
			
			}	
//		else if((uxBits & BIT_1)== BIT_1 )  //
//			{
//		    key_press = 0;	
//				
//			}
		}			
		 vTaskDelay(5);
	}
}

/*
*********************************************************************************************************
*	函 数 名: Read_the_motor_status1
*	功能说明: 读取当前电机的温度、电压和错误状态标志  
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Read_the_motor_status1(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x9A;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}



/*
*********************************************************************************************************
*	函 数 名: Read_the_motor_status2
*	功能说明: 读取当前电机的温度、电机转矩电流（MF、MG）/电机输出功率（MS）、转速、编码器位置  
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Read_the_motor_status2(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x9C;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}



/*
*********************************************************************************************************
*	函 数 名: Clear_the_motor_error_flag
*	功能说明: 清除电机错误标志命令
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Clear_the_motor_error_flag(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x9B;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}


/*
*********************************************************************************************************
*	函 数 名: Motor_close
*	功能说明: 电机关闭  ：切换到关闭状态，清除电机转动圈数及之前接收的控制指令
*	形    参: 无
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Motor_close(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x80;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Motor_operation
*	功能说明: 电机运行：将电机从关闭状态切换到开启状态，LED 由慢闪转为常亮。此时再发送控制指令即可控制电机动作。
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Motor_operation(uint32_t Motor_id) 
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x88;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Motor_stop
*	功能说明: 电机停止 ：  但不清除电机运行状态。再次发送控制指令即可控制电机动作。
*	形    参: 无
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Motor_stop(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x81;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}


/*
*********************************************************************************************************
*	函 数 名: Brake_control
*	功能说明: 抱闸控制 ：  但不清除电机运行状态。再次发送控制指令即可控制电机动作。
*	形    参: 0x00：抱闸器断电，刹车启动
						0x01：抱闸器通电，刹车释放
						0x10：读取抱闸器状态
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Brake_control(uint32_t Motor_id,u8 command)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x8C;   
  g_tCanTxMsg.Data[1] = command;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}



/*
*********************************************************************************************************
*	函 数 名: Motor_openloop_control
*	功能说明: 主机发送该命令以控制输出到电机的开环电压，数值范围-850~ 850
*	形    参: 无
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Motor_openloop_control(uint32_t Motor_id, int16_t powerControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0xA0;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&powerControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&powerControl)+1);
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: MotorSpeed_openloop_control
*	功能说明: 主机发送该命令以控制电机的速度， 控制值 speedControl 为 int32_t 类型，对应实际转速为0.01dps/LSB。
*	形    参: 无
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void MotorSpeed_closedloop_control(uint32_t Motor_id, int32_t speedControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          
	g_tCanTxMsg.Data[0] = 0xA2;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&speedControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&speedControl)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(&speedControl)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(&speedControl)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Multiloop_position_closedloop_control
*	功能说明: 多圈位置闭环控制命令1：   主机发送该命令以控制电机的位置（多圈角度）。控制值 angleControl
																		对应实际位置为 0.01degree/LSB，即 36000 代表 360°，电机转动方向由目标位置和当前位置的差值决定。
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Multiloop_position_closedloop_control1(uint32_t Motor_id, int32_t angleControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          
	g_tCanTxMsg.Data[0] = 0xA3;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&angleControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&angleControl)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(&angleControl)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(&angleControl)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Multiloop_position_closedloop_control2
*	功能说明: 多圈位置闭环控制命令2：   
				控制值 angleControl 为 int32_t 类型，对应实际位置为 0.01degree/LSB，即 36000 代表 360°，电机转动方向由目标位置和当前位置的差值决定。
				控制值 maxSpeed 限制了电机转动的最大速度，为 uint16_t 类型，对应实际转速 1dps/LSB，即 360代表 360dps。
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Multiloop_position_closedloop_control2(uint32_t Motor_id, uint16_t maxSpeed, int32_t angleControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          
	g_tCanTxMsg.Data[0] = 0xA4;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = *(uint8_t *)(&maxSpeed);
  g_tCanTxMsg.Data[3] = *((uint8_t *)(&maxSpeed)+1);
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&angleControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&angleControl)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(&angleControl)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(&angleControl)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}


/*
*********************************************************************************************************
*	函 数 名: Singleloop_position_closedloop_control1
*	功能说明: 主机发送该命令以控制电机的位置（单圈角度）  :
*	形    参: spinDirection : 0x00 代表顺时针，0x01 代表逆时针
						angleControl  
*	返 回 值: 无
*********************************************************************************************************
*/
void Singleloop_position_closedloop_control1(uint32_t Motor_id, uint8_t spinDirection, int32_t angleControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          
	g_tCanTxMsg.Data[0] = 0xA5;   
  g_tCanTxMsg.Data[1] = spinDirection;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&angleControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&angleControl)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(&angleControl)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(&angleControl)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Singleloop_position_closedloop_control2
*	功能说明: 主机发送该命令以控制电机的位置（单圈角度）  :
*	形    参: spinDirection : 0x00 代表顺时针，0x01 代表逆时针
						angleControl  
*	返 回 值: 无
*********************************************************************************************************
*/
void Singleloop_position_closedloop_control2(uint32_t Motor_id, uint8_t spinDirection, uint16_t maxSpeed,int32_t angleControl)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          
	g_tCanTxMsg.Data[0] = 0xA6;   
  g_tCanTxMsg.Data[1] = spinDirection;
	
  g_tCanTxMsg.Data[2] = *(uint8_t *)(&maxSpeed);
  g_tCanTxMsg.Data[3]	= *((uint8_t *)(&maxSpeed)+1);
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&angleControl);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(&angleControl)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(&angleControl)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(&angleControl)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Incremental_position_closed_loop1
*	功能说明: 增量位置闭环控制命令
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Incremental_position_closed_loop1(uint32_t Motor_id,int32_t angleIncrement)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0xA7;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] =	0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(& angleIncrement);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(& angleIncrement)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(& angleIncrement)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(& angleIncrement)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}
/*
*********************************************************************************************************
*	函 数 名: Incremental_position_closed_loop2
*	功能说明: 增量位置闭环控制命令
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void Incremental_position_closed_loop2(uint32_t Motor_id,uint32_t maxSpeed,int32_t angleIncrement)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0xA8;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = *(uint8_t *)(&maxSpeed);
  g_tCanTxMsg.Data[3] = *((uint8_t *)(&maxSpeed)+1);
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(& angleIncrement);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(& angleIncrement)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(& angleIncrement)+2);
  g_tCanTxMsg.Data[7] = *((uint8_t *)(& angleIncrement)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}




/*
*********************************************************************************************************
*	函 数 名: Read_the_control_parameters
*	功能说明: 读取控制参数。
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Read_the_control_parameters(uint32_t Motor_id,uint8_t index)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0xB0;   
  g_tCanTxMsg.Data[1] = index;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Set_the_control_parameters
*	功能说明: 设置控制参数
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Set_the_control_parameters(uint32_t Motor_id,uint8_t index,uint8_t Control_Parameter[6])
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0xB1;   
  g_tCanTxMsg.Data[1] = index;
	
  g_tCanTxMsg.Data[2] = Control_Parameter[0];
  g_tCanTxMsg.Data[3] = Control_Parameter[1];
  g_tCanTxMsg.Data[4] = Control_Parameter[2];
  g_tCanTxMsg.Data[5] = Control_Parameter[3];
  g_tCanTxMsg.Data[6] = Control_Parameter[4];
  g_tCanTxMsg.Data[7] = Control_Parameter[5];	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}


/*
*********************************************************************************************************
*	函 数 名: Read_encoder_data
*	功能说明: 读取编码器数据。
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Read_encoder_data(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x90;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] = 0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}


/*
*********************************************************************************************************
*	函 数 名: Write_encoder_to_ROM
*	功能说明: 写入编码器值到 ROM 作为电机零点命令
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Write_encoder_to_ROM(uint32_t Motor_id,uint16_t encoderOffset)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x91;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = *(uint8_t *)(&encoderOffset);
  g_tCanTxMsg.Data[7] =	*((uint8_t *)(&encoderOffset)+1);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Write_the_current_position_to_ROM
*	功能说明: 将电机当前编码器位置作为初始位置写入到 ROM 作为电机零点
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Write_the_current_position_to_ROM(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x19;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] =	0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}



/*
*********************************************************************************************************
*	函 数 名: Read_the_Multiloop_angle
*	功能说明: 读取多圈角度
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Read_the_Multiloop_angle(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x92;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] =	0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Read_the_Singleloop_angle
*	功能说明: 读取单圈角度
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Read_the_Singleloop_angle(uint32_t Motor_id)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x94;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
  g_tCanTxMsg.Data[4] = 0x00;
  g_tCanTxMsg.Data[5] = 0x00;
  g_tCanTxMsg.Data[6] = 0x00;
  g_tCanTxMsg.Data[7] =	0x00;	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

/*
*********************************************************************************************************
*	函 数 名: Read_the_Singleloop_angle
*	功能说明: 设置多圈角度到当前位置（写入 RAM）
*	形    参: 
*	返 回 值: 和主机发送相同
*********************************************************************************************************
*/
void Set_multiloop_angle_to_current_position(uint32_t Motor_id,int32_t motorAngle)
{
	CanTxMsg g_tCanTxMsg;			
	
	/* 填充发送参数 */
	g_tCanTxMsg.StdId = Motor_id;
	g_tCanTxMsg.ExtId = 0x00;
	g_tCanTxMsg.RTR = CAN_RTR_DATA;
	g_tCanTxMsg.IDE = CAN_ID_STD;
	
	g_tCanTxMsg.DLC = 8;          /* 每包数据支持0-8个字节，这里设置为发送8个字节 */
	g_tCanTxMsg.Data[0] = 0x95;   
  g_tCanTxMsg.Data[1] = 0x00;
  g_tCanTxMsg.Data[2] = 0x00;
  g_tCanTxMsg.Data[3] = 0x00;
	
  g_tCanTxMsg.Data[4] = *(uint8_t *)(&motorAngle);
  g_tCanTxMsg.Data[5] = *((uint8_t *)(& motorAngle)+1);
  g_tCanTxMsg.Data[6] = *((uint8_t *)(& motorAngle)+2);
  g_tCanTxMsg.Data[7] =	*((uint8_t *)(& motorAngle)+3);	
	
  CAN_Transmit(CAN2, &g_tCanTxMsg);	
}

