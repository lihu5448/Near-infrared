#include "ADS1255.h"
#include "USART1.h"
#include "stdio.h"
#include "TIM.h"

void ADS1255_write_reg(uint8_t ADS1255_command,uint8_t *WriteBuf,uint8_t len);
void ADS1255_read_reg(uint8_t ADS1255_command,uint8_t *ReadBuf,uint8_t len);
void ADS1255_write_bit(uint8_t temp);//功能:写一字节数据
uint8_t ADS1255_read_bit(void);      //功能:读一字节数据


//----------write------------------
#define ADS1255_Write_SCLK_H GPIOA->ODR |= 1<<5      //GPIO_SetBits(ADS1255_SCLK_PORT, ADS1255_SCLK_PIN)
#define ADS1255_Write_SCLK_L GPIOA->ODR &= ~(1<<5)    //GPIO_ResetBits(ADS1255_SCLK_PORT,ADS1255_SCLK_PIN)	
	
#define ADS1255_Write_CS_H   GPIOA->ODR |= 1<<4      //GPIO_SetBits(ADS1255_CS_PORT, ADS1255_CS_PIN)
#define ADS1255_Write_CS_L   GPIOA->ODR &= ~(1<<4)    //GPIO_ResetBits(ADS1255_CS_PORT,ADS1255_CS_PIN)	

#define ADS1255_Write_RST_H  GPIOB->ODR |= 1<<1     //GPIO_SetBits(ADS1255_RST_PORT, ADS1255_RST_PIN)
#define ADS1255_Write_RST_L  GPIOB->ODR &= ~(1<<1)   //GPIO_ResetBits(ADS1255_RST_PORT,ADS1255_RST_PIN)		

#define ADS1255_Write_DIN_H  GPIOA->ODR |= 1<<7       //GPIO_SetBits(ADS1255_DIN_PORT, ADS1255_DIN_PIN)
#define ADS1255_Write_DIN_L  GPIOA->ODR &= ~(1<<7)    //GPIO_ResetBits(ADS1255_DIN_PORT,ADS1255_DIN_PIN)	

#define ADS1255_Write_SYNC_H GPIOA->ODR |= 1<<3       //GPIO_SetBits(ADS1255_SYNC_PORT, ADS1255_SYNC_PIN)
#define ADS1255_Write_SYNC_L GPIOA->ODR &= ~(1<<3)    //GPIO_ResetBits(ADS1255_SYNC_PORT,ADS1255_SYNC_PIN)	
//----------read------------------
#define ADS1255_Read_DOUT ((GPIOA->IDR & (1<<6))>>6)  //GPIO_ReadInputDataBit(ADS1255_DOUT_PORT,ADS1255_DOUT_PIN)  
#define ADS1255_Read_DRDY ((GPIOA->IDR & (1<<0))>>0)   //GPIO_ReadInputDataBit(ADS1255_DRDY_PORT,ADS1255_DRDY_PIN)
 
/****************************************
功能：写一字节数据
*****************************************/
void ADS1255_write_bit(uint8_t temp)
{
	uint8_t i;
	for(i=0;i<8;i++)
	{
		ADS1255_Write_SCLK_H; 
		if(temp&0x80) 
			ADS1255_Write_DIN_H;
		else
			ADS1255_Write_DIN_L;
		temp=temp<<1;
		delay_us(1);	 
		ADS1255_Write_SCLK_L;
		delay_us(1);
	}
}

/****************************************
功能：读一字节数据
*****************************************/
uint8_t ADS1255_read_bit(void)
{
 uint8_t i;
 uint8_t date;
	for(i=0;i<8;i++)
	{
		ADS1255_Write_SCLK_H;
		date=date<<1;
		delay_us(1);
		ADS1255_Write_SCLK_L;
		date= date | ADS1255_Read_DOUT;
		delay_us(1);
	}
  return date;
}

/****************************************
功能：读DRDY引脚状态
*****************************************/
uint8_t ADS1255_DRDY(void)
{
	return ADS1255_Read_DRDY;
}

/****************************************
功能：读单次数据命令
*****************************************/
void ADS1255_RDATA(void)
{
	while(ADS1255_Read_DRDY);
	ADS1255_Write_CS_L;	
	ADS1255_write_bit(0x01);
	ADS1255_Write_CS_H;
}


/****************************************
功能:连续读数据命令
*****************************************/
void ADS1255_RDATAC(void)
{
	while(ADS1255_Read_DRDY);
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0x03);
	ADS1255_Write_CS_H;
}


/****************************************
功能:停止连续读数据命令
*****************************************/
void ADS1255_SDATAC(void)
{
	while(ADS1255_Read_DRDY);
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0x0F);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:补偿和增益自我校准命令
*****************************************/
void ADS1255_SELFCAL(void)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0xF0);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:补偿自我校准
*****************************************/
void ADS1255_SELFOCAL(void)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0xF1);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:增益自我校准
*****************************************/
void ADS1255_SELFGCAL(void)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0xF2);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:系统补偿校准
*****************************************/
void ADS1255_SYSOCAL(void)
{
	ADS1255_Write_CS_L;	
	ADS1255_write_bit(0xF3);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:系统增益校准
*****************************************/
void ADS1255_SYSGCAL(void)
{
	ADS1255_Write_CS_L;	
	ADS1255_write_bit(0xF4);
	ADS1255_Write_CS_H;	
}


/****************************************
功能:AD转换同步
*****************************************/
void ADS1255_SYNC(void)
{
	ADS1255_Write_CS_L;		
	ADS1255_write_bit(0xFC);	
	ADS1255_Write_CS_H;
}


/****************************************
功能:启动待机模式
*****************************************/
void ADS1255_ATANDBY(void)
{
	ADS1255_Write_CS_L;	
	ADS1255_write_bit(0xFD);
	ADS1255_Write_CS_H;
}


/****************************************
功能:系统复位
*****************************************/
void ADS1255_RESET(void)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0xFE);
	ADS1255_Write_CS_H;
}


/****************************************
功能:退出待机模式
*****************************************/
void ADS1255_WAKEUP(void)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0xFF);
	ADS1255_Write_CS_H;
}

/****************************************
//功能:单次读取时，读取一次ADC数据
*****************************************/
uint32_t ADS1255_OneRead_AdcData(void)
{
	uint32_t Data,Data1,Data2,Data3; 
	ADS1255_Write_CS_L;
	ADS1255_write_bit(0x01);
	delay_us(15);
	Data1 = (uint32_t)ADS1255_read_bit();
	Data2 = (uint32_t)ADS1255_read_bit();
	Data3 = (uint32_t)ADS1255_read_bit();
	ADS1255_Write_CS_H;
	Data = (Data1<<16) | (Data2<<8) | Data3;
	return (Data);
}
/****************************************
//功能:连续读取时，读取一次ADC数据
*****************************************/
uint32_t ADS1255_ContinuousRead_AdcData(void)
{
	uint32_t Data,Data1,Data2,Data3; 
	ADS1255_Write_CS_L;
	Data1 = (uint32_t)ADS1255_read_bit();
	Data2 = (uint32_t)ADS1255_read_bit();
	Data3 = (uint32_t)ADS1255_read_bit();
	ADS1255_Write_CS_H;
	Data = (Data1<<16) | (Data2<<8) | Data3;
	return (Data);
}
/****************************************
功能：ADS1255写寄存器
说明：根据要求写入寄存器和命令字
*****************************************/
void ADS1255_write_reg(uint8_t ADS1255_command,uint8_t *WriteBuf,uint8_t len)
{
	ADS1255_Write_CS_L;
	ADS1255_write_bit(ADS1255_command | 0x50);
	ADS1255_write_bit(len-1);
	for(int i=0;i<len;i++)
	{
		ADS1255_write_bit(WriteBuf[i]);
	}
	ADS1255_Write_CS_H;
}


/****************************************
功能：ADS1255读寄存器
说明：根据要求写入寄存器地址
*****************************************/
void ADS1255_read_reg(uint8_t ADS1255_command,uint8_t *ReadBuf,uint8_t len)
{
	ADS1255_Write_CS_L;
  ADS1255_write_bit(ADS1255_command | 0x10);
  ADS1255_write_bit(len-1);
	delay_us(20);//最少等待50个ADC时钟周期		
	for(int i=0;i<len;i++)
	{
		ReadBuf[i]=ADS1255_read_bit();
	}
	ADS1255_Write_CS_H;
}

/****************************************
功能：IO初始化
*****************************************/
void ADS1255_IO_Init(void)
{

	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_GPIOA, ENABLE);  //使能GPIOA的时钟
	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_GPIOB, ENABLE);  //使能GPIOB的时钟
	
	GPIO_InitTypeDef GPIO_InitStructure;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_2MHz;
	GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
	GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;	
	GPIO_InitStructure.GPIO_Pin = ADS1255_SCLK_PIN; GPIO_Init(ADS1255_SCLK_PORT,&GPIO_InitStructure); 
	GPIO_InitStructure.GPIO_Pin = ADS1255_CS_PIN;   GPIO_Init(ADS1255_CS_PORT,  &GPIO_InitStructure); 
	GPIO_InitStructure.GPIO_Pin = ADS1255_RST_PIN;  GPIO_Init(ADS1255_RST_PORT, &GPIO_InitStructure); 
	GPIO_InitStructure.GPIO_Pin = ADS1255_DIN_PIN;  GPIO_Init(ADS1255_DIN_PORT, &GPIO_InitStructure); 
	GPIO_InitStructure.GPIO_Pin = ADS1255_SYNC_PIN; GPIO_Init(ADS1255_SYNC_PORT,&GPIO_InitStructure); 
 
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
	GPIO_InitStructure.GPIO_Pin = ADS1255_DOUT_PIN; GPIO_Init(ADS1255_DOUT_PORT,&GPIO_InitStructure); 
	GPIO_InitStructure.GPIO_Pin = ADS1255_DRDY_PIN; GPIO_Init(ADS1255_DRDY_PORT,&GPIO_InitStructure);
	
	ADS1255_Write_CS_H;
	ADS1255_Write_SYNC_H;
	ADS1255_Write_SCLK_L;
	ADS1255_Write_RST_L;
	delay_ms(100);
	ADS1255_Write_RST_H;
	delay_ms(1);
	ADS1255_Write_CS_L;	
	delay_ms(1);	
}


/****************************************
功能：寄存器设置初始化,如果初始化成功返回0，失败返回1
*****************************************/
uint8_t ADS1255_config(ADC_ConfigTypeDef AdcConfig)
{
	uint8_t ReadBuf[5]={0};
	uint8_t WriteBuf[5]={0};
 
	//状态寄存器初始化---------------------------------------------------
	if(AdcConfig.AinBuf!=0)    WriteBuf[0]|=0x02;	
	//模拟多路选择器初始化---------------------------------------------------	
	WriteBuf[1]|=(AdcConfig.AIN_P<<4);
	WriteBuf[1]|=(AdcConfig.AIN_N);	
	//AD控制寄存器初始化---------------------------------------------------	
	WriteBuf[2]|=(AdcConfig.ClockOut<<5);
	WriteBuf[2]|=(AdcConfig.SenserTestCurrent<<3);	
	WriteBuf[2]|=(AdcConfig.PGA);	
	//数据速度寄存器初始化---------------------------------------------------	
	WriteBuf[3]=AdcConfig.SPS;
	//I/O控制寄存器初始化---------------------------------------------------
  WriteBuf[4]=0x00;

	ADS1255_write_reg(0x00,WriteBuf,5);
	ADS1255_read_reg(0x00,ReadBuf,5);	
 
	//寄存器配置验证---------------------------------------------------
  if((ReadBuf[0]&0x0A) != WriteBuf[0])  {return 1;}
  if((ReadBuf[1]&0xFF) != WriteBuf[1])  {return 1;}
  if((ReadBuf[2]&0xFF) != WriteBuf[2])  {return 1;}
  if((ReadBuf[3]&0xFF) != WriteBuf[3])  {return 1;}
  if((ReadBuf[4]&0xFE) != WriteBuf[4])  {return 1;}
	return 0;
}
 
/****************************************
功能：执行一次ADC内部增益和补偿校准
*****************************************/
void ADS1255_AdjSELF(void)
{
	ADS1255_WAKEUP();delay_us(15); while(ADS1255_DRDY()!=0);//唤醒设备
	ADS1255_SDATAC();delay_us(15); while(ADS1255_DRDY()!=0);	//取消连续读取数据
	ADS1255_SELFCAL();delay_us(15); while(ADS1255_DRDY()!=0);//功能命令:补偿和增益自我校准命令			 
}

/****************************************
功能：执行一次系统增益和补偿校准，调用该函数时需要保证系统输入为零
*****************************************/
void ADS1255_AdjSYS(void)
{
	ADS1255_WAKEUP(); delay_us(15); while(ADS1255_DRDY()!=0);//唤醒设备
	ADS1255_SDATAC(); delay_us(15); while(ADS1255_DRDY()!=0);	//取消连续读取数据
	ADS1255_SELFCAL();delay_us(15); while(ADS1255_DRDY()!=0);//功能命令:补偿和增益自我校准命令	
	ADS1255_SYSOCAL();delay_us(15); while(ADS1255_DRDY()!=0);//功能命令:系统补偿校准
	ADS1255_SYSGCAL();delay_us(15); while(ADS1255_DRDY()!=0);//功能命令:系统增益校准			 
}

/****************************************
//功能:把读数转化成电压值,输入分别为 ： 读回的二进制值   参考电压   内置增益
*****************************************/
double ADS1255_DataFormatting(uint32_t Data , double Vref ,uint8_t PGA)
{
	/*
	电压计算公式；
			设：AD采样的电压为Vin ,AD采样二进制值为X，参考电压为 Vr ,内部集成运放增益为G
			Vin = ( (2*Vr) / G ) * ( x / (2^23 -1))
	*/
	double ReadVoltage;
	if(Data & 0x00800000)
	{
		Data = (~Data) & 0x00FFFFFF;
		ReadVoltage = -(((double)Data) / 8388607) * ((2*Vref) / ((double)PGA));
	}
	else
	{
		ReadVoltage =  (((double)Data) / 8388607) * ((2*Vref) / ((double)PGA));
	}
	return(ReadVoltage);
}








