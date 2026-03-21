#ifndef Motor_data_process_h
#define Motor_data_process_h

#include "includes.h"

/**
 * @brief MS系列电机参数结构体
 * @note 所有角度单位为0.01度，速度单位为dps，电流单位为0.01A，电压单位为0.01V，温度单位为℃
 */
typedef struct {
    // 电机状态1相关参数
    int8_t   temperature;      // 电机温度，单位1℃
    int16_t  voltage;          // 母线电压，单位0.01V
    int16_t  current;          // 母线电流，单位0.01A
    uint8_t  motorState;       // 电机状态：0x00开启，0x10关闭
    uint8_t  errorState;       // 错误状态标志位

    // 电机状态2相关参数
    int16_t  power;            // 输出功率，范围-1000~1000
    int16_t  speed;            // 电机转速，单位1dps/LSB
    uint16_t encoder;          // 编码器位置值
	
    uint16_t encoder_last;
	
    // === 绝对位置追踪 (核心) ===
    int64_t  current_total_ticks; // 从上电开始累计的总Tick数 (软件维护的多圈位置)
	
	
    // 编码器相关参数
    uint16_t encoderRaw;       // 编码器原始位置
    uint16_t encoderOffset;    // 编码器零偏

    // 角度相关参数
    int64_t  motorAngle;       // 多圈绝对角度，单位0.01°/LSB
    uint32_t circleAngle;      // 单圈角度，单位0.01°/LSB

    // 控制参数
    int16_t  torqueLimit;      // 力矩限制
    int32_t  accelLimit;       // 加速度限制
    int32_t  speedLimit;       // 速度限制

    // 控制命令相关参数
    int16_t  powerControl;     // 开环控制值，范围-850~850
    int32_t  speedControl;     // 速度控制值，单位0.01dps/LSB
    int32_t  angleControl;     // 位置控制值，单位0.01degree/LSB
    int32_t  angleIncrement;   // 位置增量，单位0.01degree/LSB

    // 抱闸器状态
    uint8_t  BrakeState;       // 伺服器状态：0x00刹车启动，0x01刹车释放
		
		//编码器状态
		float angle_now;
		float angle_last;
		float angle_error;
		
		uint16_t motor_rotate_count;  //电机角度设置

    /* 用 encoder tick 判定“1°完成”的状态 */
    uint16_t step_prev_enc;       // 上一次用于计算增量的 encoder
    uint16_t step_accum_ticks;    // 已累计的 tick（累积到约91视作1°） =》已累计的 tick（累积到约91视作1°）
    uint8_t  step_prev_valid;     // step_prev_enc 是否有效（0/1）
		
} MS_Motor_Params_t;


void motor_data_process(CanRxMsg g_tCanRxMsg);





#endif

/***************************** 安富莱电子 www.armfly.com (END OF FILE) *********************************/
