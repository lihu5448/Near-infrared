#include "includes.h"


/*
**********************************************************************************************************
											函数声明
**********************************************************************************************************
*/
static void vTaskTaskUserIF(void *pvParameters);
static void vTaskLED(void *pvParameters);
static void vTaskMsgPro(void *pvParameters);
static void vTaskStart(void *pvParameters);
static void AppTaskCreate (void);
static void AppTaskCreate (void);
static void AppObjCreate (void);
//static void vTimerCallback(xTimerHandle pxTimer);

/*
**********************************************************************************************************
											变量声明
**********************************************************************************************************
*/
static TaskHandle_t xHandleTaskUserIF = NULL;
static TaskHandle_t xHandleTaskLED = NULL;
static TaskHandle_t xHandleTaskMsgPro = NULL;
static TaskHandle_t xHandleTaskStart = NULL;

TimerHandle_t xTimers= NULL;
QueueHandle_t xQueue1 = NULL;
QueueHandle_t xQueue2 = NULL;

// 信号量
SemaphoreHandle_t encoder_init_flag = NULL;  


// 创建事件标志组
EventGroupHandle_t Motor_rotate_event;

/* 定义全局变量 */
CanTxMsg g_tCanTxMsg;	/* 用于发送 */
CanRxMsg g_tCanRxMsg;	/* 用于接收 */
char led_flag = 0;


u8  timer_count = 0;

extern uint32_t Motor_Id;

extern void can_LedCtrl(void);
extern void can_demo(void);

/*
*********************************************************************************************************
*	函 数 名: main
*	功能说明: 标准c程序入口。
*	形    参：无
*	返 回 值: 无
*********************************************************************************************************
*/
int main(void)
{
	/* 
	  在启动调度前，为了防止初始化STM32外设时有中断服务程序执行，这里禁止全局中断(除了NMI和HardFault)。
	  这样做的好处是：
	  1. 防止执行的中断服务程序中有FreeRTOS的API函数。
	  2. 保证系统正常启动，不受别的中断影响。
	  3. 关于是否关闭全局中断，大家根据自己的实际情况设置即可。
	  在移植文件port.c中的函数prvStartFirstTask中会重新开启全局中断。通过指令cpsie i开启，__set_PRIMASK(1)
	  和cpsie i是等效的。
     */
	__set_PRIMASK(1);  
	
	/* 创建任务 */
	AppTaskCreate();

	/* 创建任务通信机制 */
	AppObjCreate();


	/* 硬件初始化 */
	bsp_Init(); 	
	
  /* 启动调度，开始执行任务 */
  vTaskStartScheduler();

	/* 
	  如果系统正常启动是不会运行到这里的，运行到这里极有可能是用于定时器任务或者空闲任务的
	  heap空间不足造成创建失败，此要加大FreeRTOSConfig.h文件中定义的heap大小：
	  #define configTOTAL_HEAP_SIZE	      ( ( size_t ) ( 17 * 1024 ) )
	*/
	while(1);
}

/*
*********************************************************************************************************
*	函 数 名: vTaskTaskUserIF
*	功能说明: 接口消息处理。
*	形    参: pvParameters 是在创建该任务时传递的形参
*	返 回 值: 无
*   优 先 级:   (数值越小优先级越低，这个跟uCOS相反)
*********************************************************************************************************
*/
static void vTaskTaskUserIF(void *pvParameters)
{
    while(1)
    {
		  Motor_control();
			vTaskDelay(10); 
	  }
}

/*
*********************************************************************************************************
*	函 数 名: vTaskLED
*	功能说明: LED闪烁，这里通过接收CAN总线消息来实现LED闪烁
*	形    参: pvParameters 是在创建该任务时传递的形参
*	返 回 值: 无
*   优 先 级: 
*********************************************************************************************************
*/
static void vTaskLED(void *pvParameters)
{
    while(1)
    {
			if(led_flag)
			{
			bsp_LedOn(1);
			bsp_LedOff(2);			
			}
			else
			{
			bsp_LedOff(1);	
			bsp_LedOn(2);				
			}
		 led_flag = !led_flag;
		 vTaskDelay(500); 
    }
}

/*
*********************************************************************************************************
*	函 数 名: vTaskMsgPro
*	功能说明: 消息处理，这里通过接收CAN总线消息来实现蜂鸣器鸣响
*	形    参: pvParameters 是在创建该任务时传递的形参
*	返 回 值: 无
*   优 先 级:  
*********************************************************************************************************
*/
static void vTaskMsgPro(void *pvParameters)
{
	 BaseType_t xResult;
   CanRxMsg CanRx_info;
	
    while(1)
    {
			xResult = xQueueReceive(xQueue1,                   /* 消息队列句柄 */
		                        (void *)&CanRx_info,  /* 存储接收到的数据到变量ucQueueMsgValue中 */
		                        (TickType_t)portMAX_DELAY);/* 设置阻塞时间 */
		
			if(xResult == pdPASS)
			{
				motor_data_process(CanRx_info);
			}
	
			
				
	//消息队列2留给串口		
			
//			xResult = xQueueReceive(xQueue2,                   /* 消息队列句柄 */
//		                        (void *)&CanRx_info,  /* 存储接收到的数据到变量ucQueueMsgValue中 */
//		                        (TickType_t)portMAX_DELAY);/* 设置阻塞时间 */
//		
//		if(xResult == pdPASS)
//			{
//			  motor_data_process( CanRx_info);
//			}				
			
			vTaskDelay(5); 
    }
}

/*
*********************************************************************************************************
*	函 数 名: vTaskStart
*	功能说明: 启动任务，也就是最高优先级任务，这里用作按键扫描和蜂鸣器处理函数。
*	形    参: pvParameters 是在创建该任务时传递的形参
*	返 回 值: 无
*   优 先 级:  
*********************************************************************************************************
*/
static void vTaskStart(void *pvParameters)
{
    while(1)
    {
			bsp_KeyScan();  /* 按键扫描 */
			vTaskDelay(10);
    }
}
				
/*
*********************************************************************************************************
*	函 数 名: AppTaskCreate
*	功能说明: 创建应用任务
*	形    参：无
*	返 回 值: 无
*********************************************************************************************************
*/
static void AppTaskCreate (void)
{
	
	xTaskCreate( vTaskLED,    		/* 任务函数  */
                 "vTaskLED",  		/* 任务名    */
                 512,         		/* stack大小，单位word，也就是4字节 */
                 NULL,        		/* 任务参数  */
                 1,           		/* 任务优先级*/
                 &xHandleTaskLED ); /* 任务句柄  */ 

	xTaskCreate( vTaskTaskUserIF,   	/* 任务函数  */
                 "vTaskUserIF",     	/* 任务名    */
                 512,               	/* 任务栈大小，单位word，也就是4字节 */
                 NULL,              	/* 任务参数  */
                 3,                 	/* 任务优先级*/
                 &xHandleTaskUserIF );  /* 任务句柄  */

	
	xTaskCreate( vTaskMsgPro,     		/* 任务函数  */
                 "vTaskMsgPro",   		/* 任务名    */
                 512,             		/* 任务栈大小，单位word，也就是4字节 */
                 NULL,           		/* 任务参数  */
                 4,               		/* 任务优先级*/
                 &xHandleTaskMsgPro );  /* 任务句柄  */
	
	
	xTaskCreate(   vTaskStart,     		/* 任务函数  */
                 "vTaskStart",   		/* 任务名    */    //按键扫描
                 512,            		/* 任务栈大小，单位word，也就是4字节 */
                 NULL,           		/* 任务参数  */
                 2,              		/* 任务优先级*/
                 &xHandleTaskStart );   /* 任务句柄  */
}

/*
*********************************************************************************************************
*	函 数 名: AppObjCreate
*	功能说明: 创建任务通信机制
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
static void AppObjCreate (void)
{
	
//	const TickType_t  xTimerPer = 100;
//	
//	xTimers = xTimerCreate("Timer",          /* 定时器名字 */
//							xTimerPer,       /* 定时器周期,单位时钟节拍 */
//							pdTRUE,          /* 周期性 */
//							(void *) 0,      /* 定时器ID */
//							vTimerCallback); /* 定时器回调函数 */

//	if(xTimers == NULL)
//	{
//		/* 没有创建成功，用户可以在这里加入创建失败的处理机制 */
//	}
	   
	/* 创建10个CanRxMsg型消息队列 */
	xQueue1 = xQueueCreate(10, sizeof(CanRxMsg));
    if( xQueue1 == 0 )
    {
        /* 没有创建成功，用户可以在这里加入创建失败的处理机制 */
    }
	
    
    
	/* 创建10个CanTxMsg型消息队列 */
	xQueue2 = xQueueCreate(10, sizeof(CanTxMsg));
    if( xQueue2 == 0 )
    {
        /* 没有创建成功，用户可以在这里加入创建失败的处理机制 */
    }
		
		
	Motor_rotate_event = xEventGroupCreate();
		if(Motor_rotate_event == NULL)
		{ 
			/* 没有创建成功，用户可以在这里加入创建失败的处理机制 */
		  }	
		
	// 	
	encoder_init_flag = xSemaphoreCreateCounting(2,2);
		if(encoder_init_flag == NULL)
		{ 
			/* 没有创建成功，用户可以在这里加入创建失败的处理机制 */
		  }	
//	if (xTimerStart(xTimers, 0) == pdPASS) 
//		{
//				;
//		} 
}

/*
*********************************************************************************************************
*	函 数 名: vTimerCallback
*	功能说明: 定时器回调函数
*	形    参: 无
*	返 回 值: 无
*********************************************************************************************************
*/
//static void vTimerCallback(xTimerHandle pxTimer)
//{
//	configASSERT(pxTimer);
//}

/***************************** 安富莱电子 www.armfly.com (END OF FILE) *********************************/


