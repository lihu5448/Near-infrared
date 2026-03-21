/*
*********************************************************************************************************
*	                                  
*	模块名称 : MS4005步进电机数据处理
*	文件名称 : motordataprocess.c
*
*********************************************************************************************************
*/
#include "includes.h"


MS_Motor_Params_t  MS4005;
extern EventGroupHandle_t Motor_rotate_event;
extern TaskHandle_t g_motor_control_task;


extern SemaphoreHandle_t encoder_init_flag;  //  二值信号量  用于读取初始编码器值 的标志位
extern SemaphoreHandle_t encoder_read_finish ;
extern TimerHandle_t xTimers;
extern uint8_t key_press ;
extern uint8_t flag;

/* ====== 编码器步进检测====== */
/* 你的编码器一圈 32768 count */
#define ENC_CPR                 32768u

/* 1°对应的encoder tick，约 32768/360 = 91.02
   这里用四舍五入的整数 91（足够稳定）
   如果你希望更精确，可用固定点算法（我也可以给）。 */
#define ENC_TICKS_PER_DEG       ((ENC_CPR + 180u) / 360u)   /* ≈ 91 */

/* 抖动/噪声过滤：小于等于此变化量的抖动忽略（按你实际噪声可调 1~5） */
#define ENC_NOISE_IGNORE_TICKS  1u

/* 防御：一次跳变太大（例如异常值/错帧）时的上限（可选）
   正常 5ms 问询不可能跳很大；若出现很大delta，宁愿丢掉这次以免误触发 */
#define ENC_DELTA_SANITY_MAX    5000u


int32_t delta;
uint32_t adelta;
int32_t d;
uint32_t ad;
void motor_data_process(CanRxMsg g_tCanRxMsg)
{	
	
//  BaseType_t xResult;
//	BaseType_t xHigherPriorityTaskWoken = pdFALSE;
	
	switch(g_tCanRxMsg.Data[0])
	  {
	   case  0x9A:    // 读取当前电机的温度、电压和错误状态标志       读取电机状态1
			  
			 MS4005.temperature = g_tCanRxMsg.Data[1];
			 MS4005.voltage = g_tCanRxMsg.Data[2]+g_tCanRxMsg.Data[3]*256;
			 MS4005.current = g_tCanRxMsg.Data[4]+g_tCanRxMsg.Data[5]*256;
		   MS4005.motorState = g_tCanRxMsg.Data[6];
			 MS4005.errorState = g_tCanRxMsg.Data[7];
			break;
		 
	   case  0x9B:   	// 清除当前电机的错误状态 ,                     读取电机状态 1 和错误标志命令相同（仅命令字节 DATA[0]不同，这里为 0x9B
			 MS4005.temperature = g_tCanRxMsg.Data[1];
			 MS4005.voltage = g_tCanRxMsg.Data[2]+g_tCanRxMsg.Data[3]*256;
			 MS4005.current = g_tCanRxMsg.Data[4]+g_tCanRxMsg.Data[5]*256;
		   MS4005.motorState = g_tCanRxMsg.Data[6];
			 MS4005.errorState = g_tCanRxMsg.Data[7];			 
			break; 
			 
		 case  0x80:    //将电机从开启状态（上电后默认状态）切换到关闭状态，清除电机转动圈数及之前接收的控制指令，LED 由常亮转为慢闪。此时电机仍然可以回复控制命令，但不会执行动作。
			 ;
			break;
			
		 case  0x88:    //将电机从关闭状态切换到开启状态，LED 由慢闪转为常亮。此时再发送控制指令即可控制电机动作。
			 ;
			break;
		 
			
		 case  0x81:    //停止电机，但不清除电机运行状态。再次发送控制指令即可控制电机动作
			 ;
			break;
		 
			
		 case  0x8C:    //控制抱闸器的开合，或者读取当前抱闸器的状态。
			  MS4005.BrakeState = g_tCanRxMsg.Data[1] ;
			break;
		 
		 case  0x9C:    // 当前电机的温度、电机输出功率（MS）、转速、编码器位置。    读取电机状态2
		 case  0xA0:    //主机发送该命令以控制输出到电机的开环电压，控制值 powerControl 为 int16_t 类型，数值范围-850~ 850，（电机电流和扭矩因电机而异）。
		 case  0xA2:    // 速度闭环控制命1 主机发送该命令以控制电机的速度， 控制值 speedControl 为 int32_t 类型，对应实际转速为0.01dps/LSB。
		 case  0xA3:    // 速度闭环控制命2 主机发送该命令以控制电机的位置（多圈角度）。控制值 angleControl 为 int32_t 类型，对应实际位置为 0.01degree/LSB，即 36000 代表 360°，电机转动方向由目标位置和当前位置的差值决定。
		 case  0xA4:    //  主机发送该命令以控制电机的位置（多圈角度） 限制了电机转动的最大速度
		 case  0xA5:    //  主机发送该命令以控制电机的位置（单圈角度）。			
		 case  0xA6:    //  主机发送该命令以控制电机的位置（单圈角度）。 限制了电机转动的最大速度			
		 case  0xA7:    //  主机发送该命令以控制电机的位置增量。		
		 case  0xA8:    //   主机发送该命令以控制电机的位置增量.  限制了电机转动的最大速度
			 MS4005.temperature = g_tCanRxMsg.Data[1];
			 MS4005.power = g_tCanRxMsg.Data[2] + g_tCanRxMsg.Data[3]*256;
			 MS4005.speed = g_tCanRxMsg.Data[4] + g_tCanRxMsg.Data[5]*256;
		   MS4005.encoder = g_tCanRxMsg.Data[6] + g_tCanRxMsg.Data[7]*256;		 
			break;
		 
		 case  0xB0:    //   读取当前电机的控制参数
			 switch(g_tCanRxMsg.Data[1])
					{
						case  0x10:    //  力矩限制
							MS4005.torqueLimit = g_tCanRxMsg.Data[4] + g_tCanRxMsg.Data[5]*256;
							break;
		 
						case  0x12:    //  加速度限制
							MS4005.accelLimit   = (uint32_t)g_tCanRxMsg.Data[4] |((uint32_t)g_tCanRxMsg.Data[4+1] << 8) |((uint32_t)g_tCanRxMsg.Data[4+2] << 16) |((uint32_t)g_tCanRxMsg.Data[4+3] << 24);
							break;
		 
			
						case  0x14:     //  速度限制
							MS4005.speedLimit = (uint32_t)g_tCanRxMsg.Data[4] |((uint32_t)g_tCanRxMsg.Data[4+1] << 8) |((uint32_t)g_tCanRxMsg.Data[4+2] << 16) |((uint32_t)g_tCanRxMsg.Data[4+3] << 24);
							break;			     
				
					};
			break;
		 
			
		 case  0xB1:    //  设置当前电机的控制参数，断电后设置的参数失效
			 switch(g_tCanRxMsg.Data[1])
					{
						case  0x10:    //  力矩限制
							MS4005.torqueLimit = g_tCanRxMsg.Data[4] + g_tCanRxMsg.Data[5]*256;
							break;
		 
						case  0x12:    //  加速度限制
							MS4005.accelLimit   = (uint32_t)g_tCanRxMsg.Data[4] |((uint32_t)g_tCanRxMsg.Data[4+1] << 8) |((uint32_t)g_tCanRxMsg.Data[4+2] << 16) |((uint32_t)g_tCanRxMsg.Data[4+3] << 24);
							break;
		 
			
						case  0x14:     //  速度限制
							MS4005.speedLimit = (uint32_t)g_tCanRxMsg.Data[4] |((uint32_t)g_tCanRxMsg.Data[4+1] << 8) |((uint32_t)g_tCanRxMsg.Data[4+2] << 16) |((uint32_t)g_tCanRxMsg.Data[4+3] << 24);
							break;			     
				
					};
			break;
		 
			 
		 case  0x90:    //  读取编码器的当前位置

			 MS4005.encoder = (uint16_t)g_tCanRxMsg.Data[2] | ((uint16_t)g_tCanRxMsg.Data[3] <<8 );
		   MS4005.encoderRaw = (uint16_t)g_tCanRxMsg.Data[4] | ((uint16_t)g_tCanRxMsg.Data[5] <<8 );
		   MS4005.encoderOffset = (uint16_t)g_tCanRxMsg.Data[6] | ((uint16_t)g_tCanRxMsg.Data[7] <<8 );
		 
       MS4005.angle_now =  (float)(MS4005.encoder)* 360.0f / 32768.0f;
		 
       if (key_press != 0 && g_motor_control_task != NULL)
          {
            xTaskNotifyGive(g_motor_control_task);
          }		 	   
			break;
		 
			
		 case  0x91:     //  写入编码器值到 ROM 作为电机零点
			 ;
			break;
		 
			
		 case  0x19:     //  写入当前位置到 ROM 作为电机零点
			 MS4005.encoderOffset = g_tCanRxMsg.Data[6] + g_tCanRxMsg.Data[7]*256;
			break;
			
		 case  0x92:     //读取多圈角度命令
			 MS4005.motorAngle =  (int64_t)g_tCanRxMsg.Data[1] |((int64_t)g_tCanRxMsg.Data[2] << 8) |((int64_t)g_tCanRxMsg.Data[3] << 16) |
														((int64_t)g_tCanRxMsg.Data[4] << 24) |((int64_t)g_tCanRxMsg.Data[5] << 32)|((int64_t)g_tCanRxMsg.Data[6] << 40) |((int64_t)g_tCanRxMsg.Data[7] << 48);
			break;
		 
			 
		 case  0x94:     // 读取单圈角度 
			 MS4005.circleAngle = (uint32_t)g_tCanRxMsg.Data[4] |((uint32_t)g_tCanRxMsg.Data[5] << 8) |((uint32_t)g_tCanRxMsg.Data[6] << 16) |((uint32_t)g_tCanRxMsg.Data[7] << 24);
			break;
		 
			
		 case  0x95:     //设置多圈角度到当前位置（写入 RAM）
			 ;
			break;
		 
		 default :
			 ;
			 break;
	  
	  }	

}




