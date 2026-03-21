#ifndef __ADS1256_H_H
#define __ADS1256_H_H

#include "stm32f0xx.h"


/********************************************************************/

#define	ADS1255_SCLK_PORT  GPIOA
#define ADS1255_SCLK_PIN   GPIO_Pin_5
 
#define	ADS1255_CS_PORT    GPIOA
#define ADS1255_CS_PIN     GPIO_Pin_4

#define	ADS1255_RST_PORT   GPIOB
#define ADS1255_RST_PIN    GPIO_Pin_1
 
#define	ADS1255_DIN_PORT   GPIOA
#define ADS1255_DIN_PIN    GPIO_Pin_7

#define	ADS1255_SYNC_PORT  GPIOA
#define ADS1255_SYNC_PIN   GPIO_Pin_3

#define	ADS1255_DOUT_PORT  GPIOA
#define ADS1255_DOUT_PIN   GPIO_Pin_6

#define	ADS1255_DRDY_PORT  GPIOA
#define ADS1255_DRDY_PIN   GPIO_Pin_0
 
 
typedef enum
{
  AdcSpeed_2_5SPS   = 0x03,  
  AdcSpeed_5SPS     = 0x13, 
  AdcSpeed_10SPS    = 0x23, 
  AdcSpeed_15SPS    = 0x33, 
  AdcSpeed_25SPS    = 0x43, 
  AdcSpeed_30SPS    = 0x53, 
  AdcSpeed_50SPS    = 0x63, 
  AdcSpeed_60SPS    = 0x72, 
  AdcSpeed_100SPS   = 0x82, 
  AdcSpeed_500SPS   = 0x92, 
  AdcSpeed_1000SPS  = 0xA1, 
  AdcSpeed_2000SPS  = 0xB0, 
  AdcSpeed_3750SPS  = 0xC0, 
  AdcSpeed_7500SPS  = 0xD0, 
  AdcSpeed_15000SPS = 0xE0, 
  AdcSpeed_30000SPS = 0xF0 	
}AdcSps_TypeDef;//ADC采样率

typedef enum
{
  AdcAin_AIN0    = 0x00, 
  AdcAin_AIN1    = 0x01, 
  AdcAin_AIN2    = 0x02, 
  AdcAin_AIN3    = 0x03, 
  AdcAin_AIN4    = 0x04, 
  AdcAin_AIN5    = 0x05, 
  AdcAin_AIN6    = 0x06, 
  AdcAin_AIN7    = 0x07, 
  AdcAin_AINCOM  = 0x08	
}AdcAin_TypeDef;//ADC输入通道


typedef enum
{
  AdcPga_GAN1    = 0x00,  //1倍放大
  AdcPga_GAN2    = 0x01,  //2倍放大 
  AdcPga_GAN4    = 0x02,  //4倍放大 
  AdcPga_GAN8    = 0x03,  //8倍放大 
  AdcPga_GAN16   = 0x04,  //16倍放大 
  AdcPga_GAN32   = 0x05,  //32倍放大 
  AdcPga_GAN64   = 0x06	  //64倍放大
}AdcPga_TypeDef;//ADC内部可编程放大器


typedef enum
{
  AdcTestCurrent_OFF    = 0x00,//关闭
  AdcTestCurrent_500nA  = 0x01,//0.5uA 
  AdcTestCurrent_2uA    = 0x02,//2uA	
  AdcTestCurrent_10uA   = 0x03,//10uA 
}AdcTestCurrent_TypeDef;//传感器存在测试电流


typedef enum
{
  AdcClockOut_OFF  = 0x00,//时钟输出关闭 
  AdcClockOut_NC1  = 0x01,//时钟输出1分频 
  AdcClockOut_NC2  = 0x02,//数字输出2分频
  AdcClockOut_NC4  = 0x03,//数字输出4分频 
}AdcClockOut_TypeDef;//某些需要使用ADC时钟同步功能有用


typedef enum
{
  AdcInBuf_OFF = 0x00,//ADC输入缓冲器关闭  
  AdcInBuf_ON  = 0x01,//ADC输入缓冲器打开 
}AdcInBuf_TypeDef;//ADC输入缓冲器，打开可以增加ADC输入阻抗，但是会引入额外的噪声、误差，相当于加一个电压跟随运放


typedef struct
{
	AdcInBuf_TypeDef AinBuf;//输入缓冲器开关
  AdcAin_TypeDef AIN_P;//ADC输入高通道
  AdcAin_TypeDef AIN_N;//ADC输入低通道
	AdcClockOut_TypeDef ClockOut;//时钟输出配置
	AdcTestCurrent_TypeDef SenserTestCurrent;//传感器监测电流，正常采集数据时该电流必须关闭
	AdcPga_TypeDef PGA;//ADC内置放大器配置
	AdcSps_TypeDef SPS;//ADC的采样速度
	double ADC_RefVol;//ADC参考源电压
}ADC_ConfigTypeDef; 

/*



*/


/*****************************************************************************
                        Function Declare                                  
*****************************************************************************/
void ADS1255_IO_Init(void); //IO初始化
uint8_t ADS1255_config(ADC_ConfigTypeDef AdcConfig);//寄存器配置
void ADS1255_AdjSELF(void);//进行一次内部校准
void ADS1255_AdjSYS(void);//进行一次系统校准，调用该函数时需要保证系统输入为零（输入短接）
	
uint8_t ADS1255_DRDY(void); //功能：读DRDY引脚状态
uint32_t ADS1255_OneRead_AdcData(void);
uint32_t ADS1255_ContinuousRead_AdcData(void);//读取一次数据，调用该函数前提是已经发送了连续读取数据指令
double ADS1255_DataFormatting(uint32_t Data , double Vref ,uint8_t PGA); //功能:把读数转化成电压值,输入分别为 ： 读回的二进制值   参考电压   内置增益
 
void ADS1255_RDATA(void);    //功能命令:读单次数据命令

void ADS1255_RDATAC(void);   //功能命令:连续读数据命令
void ADS1255_SDATAC(void);   //功能命令:停止连续读数据命令

void ADS1255_SELFCAL(void);  //功能命令:补偿和增益自我校准命令
void ADS1255_SELFOCAL(void); //功能命令:补偿自我校准
void ADS1255_SELFGCAL(void); //功能命令:增益自我校准
void ADS1255_SYSOCAL(void);  //功能命令:系统补偿校准
void ADS1255_SYSGCAL(void);  //功能命令:系统增益校准
void ADS1255_SYNC(void);     //功能命令:AD转换同步
void ADS1255_ATANDBY(void);  //功能命令:启动待机模式
void ADS1255_RESET(void);    //功能命令:系统复位
void ADS1255_WAKEUP(void);   //功能命令:退出待机模式

//-------------------------------------------------------------------------------//
#endif
