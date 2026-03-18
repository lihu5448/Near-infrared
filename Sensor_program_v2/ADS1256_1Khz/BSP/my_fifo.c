/**************************************************
 * all rights reserved
 * 执行标准：GB/T 28169—2011
 * 当前版本：V1.0
 * 编写者：邓强\492841230@qq.com
 * 修改时间： 
 * 修改内容：xxxxxxxx
 **************************************************/


#include "my_fifo.h"
#include "string.h" 

union UNION_UINT8 g_myunion;
TYPE_FIFO_DATA g_fifo_data[FIFO_NABER];

uint32_t fifo_count_space(uint32_t stare,uint32_t end,uint32_t light);
/****************************************************************************************
*函数功能:初始化FIFO
*形    参:无
*返 回 值:无
*说    明:无
*****************************************************************************************/
void fifo_init(void)
{
	uint32_t i;
	
	for(i=0;i<FIFO_NABER;i++)
	{
		g_fifo_data[i].apply_enable=false;
  }
}

/****************************************************************************************
*函数功能:申請FIFO
*形    参:
    uint32_t *fifo_naber :分配的fifo编号
    uint32_t datalight   :存储单个数据占用的空间
    uint32_t light       :fifo空间
*返 回 值:是否成功，成功为：true   失败为：false
*说    明:无
*****************************************************************************************/
bool fifo_apply(uint32_t *fifo_naber,uint32_t datalight,uint32_t light)
{
	uint32_t i;
	uint32_t starpiont;
	
	for(i=0;i<FIFO_NABER;i++)
	{
		if(g_fifo_data[i].apply_enable==false)
		{
			if(i==0)
				starpiont=0;
			else
				starpiont=g_fifo_data[i].end_data+1;
			
			if(FIFO_LIGHT_UINT8_T-starpiont<datalight*light) break;//如果空间不够则反馈申请失败
			
			g_fifo_data[i].apply_enable=true;
			g_fifo_data[i].start_data=starpiont;
			g_fifo_data[i].end_data  =starpiont+datalight*light-1;
			g_fifo_data[i].cur_piont =0;
			g_fifo_data[i].end_piont =0;
			g_fifo_data[i].fifo_light=light;
			g_fifo_data[i].rema_light=light;
			*fifo_naber=i;//申请的fifo编号
			return(true);//反馈申请成功
    }
  }
	
//	error_record(ERROR_FIFO_INSUFF,sys_tem,
//	             __LINE__,__FILE__,sizeof(__FILE__),
//	             "FIFO space is insufficient",sizeof("FIFO space is insufficient"));//错误记录	
	return(false);
}

/****************************************************************************************
*函数功能:计算剩余空间
*形    参:stare：数据读取指针
          end：数据存入指针
          light：fifo长度
*返 回 值:剩余长度
*说    明:无
*****************************************************************************************/
uint32_t fifo_count_space(uint32_t stare,uint32_t end,uint32_t light)
{
	if(end>=stare)
	   return(light-end+stare);
	else
	   return(stare-end);	
}

/****************************************************************************************
*函数功能:清除fifo里面全部内容
*形    参:fifo_naber：申请的fifo编号
*返 回 值:是否成功，成功为：true   失败为：false
*说    明:无
*****************************************************************************************/
bool fifo_clear(uint32_t fifo_naber)
{
	if(fifo_naber>FIFO_NABER) return(false);
	
	g_fifo_data[fifo_naber].rema_light=g_fifo_data[fifo_naber].fifo_light;//剩余fifo空间
	g_fifo_data[fifo_naber].cur_piont=0;//结束指针
	g_fifo_data[fifo_naber].end_piont=0;//开始指针
	return(true);//反馈清除成功	
}

/****************************************************************************************
*函数功能:读取FIFO剩余空间
*形    参:fifo_naber：申请的fifo编号
*返 回 值:剩余空间
*说    明:无
*****************************************************************************************/
uint32_t fifo_remalight(uint32_t fifo_naber)
{
	if(fifo_naber>FIFO_NABER)
		return(0);
	else
	  return(g_fifo_data[fifo_naber].rema_light);
}

/****************************************************************************************
*函数功能:读取FIFO已经存入的数据数量
*形    参:fifo_naber：申请的fifo编号
*返 回 值:剩余空间
*说    明:无
*****************************************************************************************/
uint32_t fifo_indata_light(uint32_t fifo_naber)
{
	if(fifo_naber>FIFO_NABER)
		return(0);
	else
	  return(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light);
}

/****************************************************************************************
*函数功能:存入n个值到FIFO
*形    参:fifo_naber：申请的fifo编号
          *indata：存入数据的指正
          light：存入数据长度 
*返 回 值:是否成功，成功为：true   失败为：false
*说    明:无
*****************************************************************************************/
bool fifo_goint_uint8_t(uint32_t fifo_naber,uint8_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_u8[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_int8_t(uint32_t fifo_naber,int8_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_8[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_uint16_t(uint32_t fifo_naber,uint16_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>1;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_u16[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_int16_t(uint32_t fifo_naber,int16_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>1;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_16[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_uint32_t(uint32_t fifo_naber,uint32_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>2;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_u32[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_int32_t(uint32_t fifo_naber,int32_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>2;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light)  g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_32[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_float(uint32_t fifo_naber,float *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>2;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_float[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_uint64_t(uint32_t fifo_naber,uint64_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>3;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_u64[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_int64_t(uint32_t fifo_naber,int64_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>3;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_64[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

bool fifo_goint_double(uint32_t fifo_naber,double *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER) return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].rema_light<light)   return(false);
	piont=g_fifo_data[fifo_naber].start_data>>3;
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].end_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].end_piont=0;
		g_myunion.u_double[piont+g_fifo_data[fifo_naber].end_piont]=indata[i];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);
	return(true);
}

/********************************************************************* *******************
*函数功能:从FIFO读出n个值
*形    参:fifo_naber：申请的fifo编号
          *indata：读取数据的指正
          light：读取数据长度 
*返 回 值:是否成功，成功为：true   失败为：false
*说    明:无
*****************************************************************************************/
bool fifo_read_uint8_t(uint32_t fifo_naber,uint8_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_u8[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_int8_t(uint32_t fifo_naber,int8_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_8[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_uint16_t(uint32_t fifo_naber,uint16_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>1;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_u16[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_int16_t(uint32_t fifo_naber,int16_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>1;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		*(indata+i)=g_myunion.u_16[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_uint32_t(uint32_t fifo_naber,uint32_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>2;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_u32[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_int32_t(uint32_t fifo_naber,int32_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>2;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_32[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_float(uint32_t fifo_naber,float *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>2;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_float[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}


bool fifo_read_uint64_t(uint32_t fifo_naber,uint64_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>3;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_u64[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_int64_t(uint32_t fifo_naber,int64_t *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>3;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_64[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}

bool fifo_read_double(uint32_t fifo_naber,double *indata,uint32_t light)
{
	uint32_t piont=0;
	uint32_t i;
	
	if(fifo_naber>FIFO_NABER)            return(false);
	if(g_fifo_data[fifo_naber].apply_enable==false)return(false);
	if(g_fifo_data[fifo_naber].fifo_light-g_fifo_data[fifo_naber].rema_light<light)   return(false);
	
	piont=g_fifo_data[fifo_naber].start_data>>3;
	
	for(i=0;i<light;i++)
	{
		if(++g_fifo_data[fifo_naber].cur_piont>=g_fifo_data[fifo_naber].fifo_light) g_fifo_data[fifo_naber].cur_piont=0;
		indata[i]=g_myunion.u_double[piont+g_fifo_data[fifo_naber].cur_piont];
  }
	g_fifo_data[fifo_naber].rema_light=fifo_count_space(g_fifo_data[fifo_naber].cur_piont,
                 	                                    g_fifo_data[fifo_naber].end_piont,
	                                                    g_fifo_data[fifo_naber].fifo_light);		
	return(true);
}










