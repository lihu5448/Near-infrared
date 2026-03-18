#include "includes.h"

/* CAN1的引脚，时钟定义 */
#define CANx                       CAN2
#define CAN_CLK                    RCC_APB1Periph_CAN2
#define CAN_RX_PIN                 GPIO_Pin_12
#define CAN_TX_PIN                 GPIO_Pin_13
#define CAN_GPIO_TX_PORT           GPIOB
#define CAN_GPIO_TX_CLK            RCC_AHB1Periph_GPIOB
#define CAN_GPIO_RX_PORT           GPIOB
#define CAN_GPIO_RX_CLK            RCC_AHB1Periph_GPIOB
#define CAN_AF_PORT                GPIO_AF_CAN2
#define CAN_RX_SOURCE              GPIO_PinSource12
#define CAN_TX_SOURCE              GPIO_PinSource13

/*
	应用层协议:（自定义简单协议）	
	01  01    --- 控制LED指示灯翻转 
	              第1个字节是命令代码
				  第2个字节表示指示灯序号(1-4)
	02  00    --- 控制蜂鸣器
	              第1个字节表示命令代码，
	              第2个字节固定为01，表示鸣叫1次
*/


/* 定义全局变量 */
extern CanTxMsg g_tCanTxMsg;	/* 用于发送 */
extern CanRxMsg g_tCanRxMsg;	/* 用于接收 */

extern TimerHandle_t xTimers;
extern QueueHandle_t xQueue1;
extern QueueHandle_t xQueue2;

/*
*********************************************************************************************************
*	函 数 名: can_NVIC_Config
*	功能说明: 配置CAN中断
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/  

static void can_NVIC_Config(void)
{
	NVIC_InitTypeDef  NVIC_InitStructure;
	
	NVIC_InitStructure.NVIC_IRQChannel = CAN2_RX0_IRQn;;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0x01;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0x00;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
	
	/* CAN FIFO0 消息接收中断使能 */ 
	CAN_ITConfig(CANx, CAN_IT_FMP0, ENABLE);	
}
/*
*********************************************************************************************************
*	函 数 名: bsp_InitCan2
*	功能说明: 配置CAN硬件,设置波特率为1Mbps
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
void bsp_InitCan2(void)
{
	GPIO_InitTypeDef  GPIO_InitStructure;
	CAN_InitTypeDef        CAN_InitStructure;
	CAN_FilterInitTypeDef  CAN_FilterInitStructure;

	/* CAN GPIOs 配置*/
	/* 使能GPIO时钟 */
	RCC_AHB1PeriphClockCmd(CAN_GPIO_TX_CLK|CAN_GPIO_RX_CLK, ENABLE);

	/* 引脚映射为CAN功能  */
	GPIO_PinAFConfig(CAN_GPIO_RX_PORT, CAN_RX_SOURCE, CAN_AF_PORT);
	GPIO_PinAFConfig(CAN_GPIO_TX_PORT, CAN_TX_SOURCE, CAN_AF_PORT); 

	/* 配置 CAN RX 和 TX 引脚 */
	GPIO_InitStructure.GPIO_Pin = CAN_RX_PIN;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
	GPIO_InitStructure.GPIO_PuPd  = GPIO_PuPd_UP;
	GPIO_Init(CAN_GPIO_RX_PORT, &GPIO_InitStructure);

	GPIO_InitStructure.GPIO_Pin = CAN_TX_PIN;
	GPIO_Init(CAN_GPIO_TX_PORT, &GPIO_InitStructure);

	/* CAN配置*/  
	/* 使能CAN时钟 */
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1, ENABLE);
	RCC_APB1PeriphClockCmd(CAN_CLK, ENABLE);

	/* 复位CAN寄存器 */
	CAN_DeInit(CANx);
	
	/*
		TTCM = time triggered communication mode
		ABOM = automatic bus-off management 
		AWUM = automatic wake-up mode
		NART = no automatic retransmission
		RFLM = receive FIFO locked mode 
		TXFP = transmit FIFO priority		
	*/
	CAN_InitStructure.CAN_TTCM = DISABLE;			/* 禁止时间触发模式（不生成时间戳), T  */
	CAN_InitStructure.CAN_ABOM = DISABLE;			/* 禁止自动总线关闭管理 */
	CAN_InitStructure.CAN_AWUM = DISABLE;			/* 禁止自动唤醒模式 */
	CAN_InitStructure.CAN_NART = DISABLE;			/* 禁止仲裁丢失或出错后的自动重传功能 */
	CAN_InitStructure.CAN_RFLM = DISABLE;			/* 禁止接收FIFO加锁模式 */
	CAN_InitStructure.CAN_TXFP = DISABLE;			/* 禁止传输FIFO优先级 */
	CAN_InitStructure.CAN_Mode = CAN_Mode_Normal;	/* 设置CAN为正常工作模式 */
	
	/* 
		CAN 波特率 = RCC_APB1Periph_CAN1 / Prescaler / (SJW + BS1 + BS2);
		
		SJW = synchronisation_jump_width 
		BS = bit_segment
		
		本例中，设置CAN波特率为1Mbsp		
		CAN 波特率 = 420000000 / 2 / (1 + 12 + 8) / = 1Mbsp		
	*/
	CAN_InitStructure.CAN_SJW = CAN_SJW_1tq;
	CAN_InitStructure.CAN_BS1 = CAN_BS1_12tq;
	CAN_InitStructure.CAN_BS2 = CAN_BS2_8tq;
	CAN_InitStructure.CAN_Prescaler = 2;
	CAN_Init(CANx, &CAN_InitStructure);
	
	/* 设置CAN滤波器0 */
	CAN_FilterInitStructure.CAN_FilterNumber = 14;		/* 滤波器序号 */
	CAN_FilterInitStructure.CAN_FilterMode = CAN_FilterMode_IdMask;		/* 滤波器模式，设置ID掩码模式 */
	CAN_FilterInitStructure.CAN_FilterScale = CAN_FilterScale_32bit;	/* 32位滤波 */
	CAN_FilterInitStructure.CAN_FilterIdHigh = 0x0000;					/* 掩码后ID的高16bit */
	CAN_FilterInitStructure.CAN_FilterIdLow = 0x0000;					/* 掩码后ID的低16bit */
	CAN_FilterInitStructure.CAN_FilterMaskIdHigh = 0x0000;				/* ID掩码值高16bit */
	CAN_FilterInitStructure.CAN_FilterMaskIdLow = 0x0000;				/* ID掩码值低16bit */
	CAN_FilterInitStructure.CAN_FilterFIFOAssignment = CAN_FIFO0;		/* 滤波器绑定FIFO 0 */
	CAN_FilterInitStructure.CAN_FilterActivation = ENABLE;				/* 使能滤波器 */
	CAN_FilterInit(&CAN_FilterInitStructure);
    
  can_NVIC_Config();
}     



/*
*********************************************************************************************************
*	函 数 名: CAN2_RX0_IRQHandler
*	功能说明: CAN中断服务程序.
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/ 
void CAN2_RX0_IRQHandler(void)
{
	BaseType_t xHigherPriorityTaskWoken = pdFALSE;
	
	CAN_Receive(CAN2, CAN_FIFO0, &g_tCanRxMsg);
	if ((g_tCanRxMsg.StdId == 0x141) && (g_tCanRxMsg.IDE == CAN_ID_STD) && (g_tCanRxMsg.DLC == 8))
	{
        xQueueSendFromISR(xQueue1,
						(void *)&(g_tCanRxMsg),
						&xHigherPriorityTaskWoken);
		portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
	}
}



