//=============================================================================
//文件名称：usart1.c
//功能概要：串口1驱动文件
//更新时间：2014-01-04
//=============================================================================

#include "USART1.h"
#include "my_fifo.h"
#include "string.h"

#define UART1_SendBufLen 256
uint8_t UART1_SendBuf[UART1_SendBufLen];
volatile uint8_t  UART1_STATE=0;
uint32_t UART1_FifoNaber=0;


/* USART初始化 */
void USART1_Init(uint32_t BaudRate)
{
	GPIO_InitTypeDef GPIO_InitStructure;
	USART_InitTypeDef USART_Initstructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	DMA_InitTypeDef DMA_InitStructure;

	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_DMA1,ENABLE);
	RCC_AHBPeriphClockCmd(RCC_AHBPeriph_GPIOA, ENABLE);  //使能GPIOA的时钟
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);//使能USART的时钟
	
	/* USART1的端口配置 */
	GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_1);//配置PA9成第二功能引脚	TX //GPIO_PinSource2
	GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_1);//配置PA10成第二功能引脚  RX	 //GPIO_PinSource3

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;  // GPIO_Pin_2 | GPIO_Pin_3;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
	GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	USART_Initstructure.USART_BaudRate = BaudRate;
	USART_Initstructure.USART_Parity   =USART_Parity_No;
	USART_Initstructure.USART_WordLength =USART_WordLength_8b; 
	USART_Initstructure.USART_StopBits  =USART_StopBits_1;
	USART_Initstructure.USART_Mode     = USART_Mode_Rx|USART_Mode_Tx;
	USART_Initstructure.USART_HardwareFlowControl =USART_HardwareFlowControl_None;
	USART_Init(USART1,&USART_Initstructure);

	USART_ClearFlag(USART1,USART_FLAG_TC);
	USART_ITConfig(USART1,USART_IT_RXNE,ENABLE);//使能接收中断
	NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x01;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
	
	USART_DMACmd(USART1,USART_DMAReq_Tx,ENABLE);
	USART_Cmd(USART1,ENABLE);      // 使能串口

	DMA_InitStructure.DMA_BufferSize = UART1_SendBufLen;  // 缓存大小
	DMA_InitStructure.DMA_M2M = DMA_M2M_Disable;    // 内存到内存关闭
	DMA_InitStructure.DMA_Mode = DMA_Mode_Normal;   // 普通模式
	DMA_InitStructure.DMA_DIR = DMA_DIR_PeripheralDST;  // 内存到外设
	DMA_InitStructure.DMA_Priority = DMA_Priority_High; // DMA通道优先级
	DMA_InitStructure.DMA_MemoryInc = DMA_MemoryInc_Enable;// 内存地址递增
	DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&USART1->TDR;   // 外设地址   
	DMA_InitStructure.DMA_PeripheralInc =  DMA_PeripheralInc_Disable;// 外设地址不变
	DMA_InitStructure.DMA_MemoryDataSize = DMA_MemoryDataSize_Byte; // 内存数据长度
	DMA_InitStructure.DMA_MemoryBaseAddr = (uint32_t)UART1_SendBuf;   // 定义内存基地址
	DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;//外设数据长度
	DMA_Init(DMA1_Channel2,&DMA_InitStructure);
	DMA_ClearITPendingBit(DMA1_IT_TC2); // 清除一次DMA中断标志
	DMA_ITConfig(DMA1_Channel2,DMA_IT_TC,ENABLE);// 使能DMA传输完成中断
	NVIC_InitStructure.NVIC_IRQChannel = DMA1_Channel2_3_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPriority = 0x02;
	NVIC_Init(&NVIC_InitStructure);
	//DMA_Cmd(DMA1_Channel2,ENABLE);//开机发送一次DMA数据
	fifo_apply(&UART1_FifoNaber,1,100);//申请fifo
}


/*******************************************************************
  * @brief  串口发数据
  * @param  无
  * @retval 无
********************************************************************/
void USART1_SendBuf(uint8_t *buf,uint32_t len) 
{
	uint32_t i=0;
	for(i=0;i<len;i++)
	{
		/* 等待发送完毕 */
		while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET);
		/* 发送一个字节数据到USART2 */
		USART_SendData(USART1,buf[i]);
	}
}


/*********************************************************************
  * @brief  DMA1串口发数据
  * @param  无
  * @retval 1代表发送成功，0代表DMA正忙发送失败
********************************************************************/

uint8_t USART1_DmaSendBuf(uint8_t *buf,uint32_t len) 
{
	if(UART1_STATE==0)
	{
		DMA_Cmd(DMA1_Channel2,DISABLE); // 发送完成先关掉DMA通道
		memcpy(UART1_SendBuf,buf,len);
		DMA1_Channel2->CMAR = (uint32_t)UART1_SendBuf;
		DMA1_Channel2->CNDTR = len;
		
		DMA1->IFCR = DMA1_IT_TC2 | DMA1_IT_HT2 | DMA1_IT_TE2;/*lihu*/
		USART1->ICR = USART_FLAG_TC; /*lihu*/
		
		UART1_STATE=1;
		DMA_Cmd(DMA1_Channel2,ENABLE); // 再打开DMA通道	
		return 1;
	}	
	else 
		return 0;
}
		


/*********************************************************************
  * @brief  DMA1_Channel1中断服务函数
  * @param  无
  * @retval 无
********************************************************************/
void DMA1_Channel2_3_IRQHandler(void) 
{ 
	if(DMA_GetITStatus(DMA1_IT_TC2) != RESET) /*判断DMA传输完成中断*/                     
	{
		
		UART1_STATE = 0;// send over
	}
	DMA_ClearITPendingBit(DMA1_IT_TC2); /*清除DMA中断标志位*/                    
}



/*******************************************************************
  * @brief  USART1中断函数
  * @param  无
  * @retval 无
******************************************************************/
void USART1_IRQHandler(void)
{
	uint8_t UsartData=0;
	if(USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
	{
		USART_ClearITPendingBit(USART1,USART_IT_RXNE);
		UsartData=USART_ReceiveData(USART1);
  } 
	else if(USART_GetITStatus(USART1, USART_IT_ORE) != RESET) 
	{
		USART_ClearITPendingBit(USART1,USART_IT_ORE); 
		UsartData=USART_ReceiveData(USART1);
  } 
	else if(USART_GetITStatus(USART1, USART_IT_PE) != RESET)  
	{
		USART_ClearITPendingBit(USART1,USART_IT_PE);
		UsartData=USART_ReceiveData(USART1);
  } 
	fifo_goint_uint8_t (UART1_FifoNaber,&UsartData,1);
}


/******************************************************************
  * @brief  Retargets the C library printf function to the USART.
  * @param  None
  * @retval None
********************************************************************/
PUTCHAR_PROTOTYPE
{
	while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET){}
  USART_SendData(USART1, (uint8_t) ch);
  return ch;
}


