/*
*********************************************************************************************************
*	                                  
*	模块名称 : CAN网络演示程序。
*	文件名称 : can_network.h
*	版    本 : V1.3
*	说    明 : 头文件
*	修改记录 :
*		版本号  日期       作者      说明
*		v1.3    2015-01-29 Eric2013  首发
*
*	Copyright (C), 2015-2016, 安富莱电子 www.armfly.com
*
*********************************************************************************************************
*/


#ifndef  _Motor_control_h
#define  _Motor_control_h

#include "includes.h"


/**
 * @brief CAN命令发送结果枚举
 */
typedef enum {
    MS_CMD_SUCCESS = 0,      // 命令发送成功且收到正确响应
    MS_CMD_NO_RESPONSE,      // 未收到响应
    MS_CMD_RESPONSE_ERROR,   // 响应数据错误
    MS_CMD_MOTOR_ERROR,      // 电机报告错误状态
    MS_CMD_TIMEOUT,          // 响应超时
    MS_CMD_INVALID           // 无效命令
} MS_Command_Result_t;




/* 供外部调用的函数声明 */

void Motor_init(void);

void Motor_control(void);

void bsp_InitCan2(void);

void Read_the_motor_status1(uint32_t Motor_id);
void Read_the_motor_status2(uint32_t Motor_id);
void Clear_the_motor_error_flag(uint32_t Motor_id);

void Motor_close(uint32_t Motor_id);
void Motor_operation(uint32_t Motor_id) ;
void Motor_stop(uint32_t Motor_id);
void Brake_control(uint32_t Motor_id,u8 command);
void Motor_openloop_control(uint32_t Motor_id, int16_t powerControl);
void MotorSpeed_closedloop_control(uint32_t Motor_id, int32_t speedControl);
void Multiloop_position_closedloop_control1(uint32_t Motor_id, int32_t angleControl);
void Multiloop_position_closedloop_control2(uint32_t Motor_id, uint16_t maxSpeed, int32_t angleControl);
void Singleloop_position_closedloop_control1(uint32_t Motor_id, uint8_t spinDirection, int32_t angleControl);
void Singleloop_position_closedloop_control2(uint32_t Motor_id, uint8_t spinDirection, uint16_t maxSpeed,int32_t angleControl);

void Incremental_position_closed_loop1(uint32_t Motor_id,int32_t angleIncrement);
void Incremental_position_closed_loop2(uint32_t Motor_id,uint32_t maxSpeed,int32_t angleIncrement);
void Read_the_control_parameters(uint32_t Motor_id,uint8_t index);
void Set_the_control_parameters(uint32_t Motor_id,uint8_t index,uint8_t Control_Parameter[6]);

void Read_encoder_data(uint32_t Motor_id);
void Write_encoder_to_ROM(uint32_t Motor_id,uint16_t encoderOffset);
void Write_the_current_position_to_ROM(uint32_t Motor_id);
void Read_the_Multiloop_angle(uint32_t Motor_id);
void Read_the_Singleloop_angle(uint32_t Motor_id);
void Set_multiloop_angle_to_current_position(uint32_t Motor_id,int32_t motorAngle);



#endif

/***************************** 安富莱电子 www.armfly.com (END OF FILE) *********************************/
