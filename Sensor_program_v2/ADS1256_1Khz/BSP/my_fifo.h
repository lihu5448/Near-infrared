/**************************************************
 * all rights reserved
 * 执行标准：GB/T 28169—2011
 * 当前版本：V1.0
 * 编写者：邓强\492841230@qq.com
 * 修改时间： 
 * 修改内容：xxxxxxxx
 **************************************************/


#ifndef __MY_FIFO_H
#define __MY_FIFO_H

#include "stm32f0xx.h"
#include "stdbool.h"
#define false 0
#define true  1
//#define bool  uint8_t
	
#define FIFO_NABER           (uint32_t)(2)     //最大申请的FIFO数量
#define FIFO_LIGHT_UINT8_T   (uint32_t)(128)   //FIFO总占用的存储长度
#define FIFO_LIGHT_UINT16_T  (FIFO_LIGHT_UINT8_T>>1)  //FIFO存储长度
#define FIFO_LIGHT_INT16_T   (FIFO_LIGHT_UINT8_T>>1)  //FIFO存储长度
#define FIFO_LIGHT_UINT32_T  (FIFO_LIGHT_UINT8_T>>2)  //FIFO存储长度
#define FIFO_LIGHT_INT32_T   (FIFO_LIGHT_UINT8_T>>2)  //FIFO存储长度
#define FIFO_LIGHT_FLOAT     (FIFO_LIGHT_UINT8_T>>2)  //FIFO存储长度
#define FIFO_LIGHT_UINT64_T  (FIFO_LIGHT_UINT8_T>>3)  //FIFO存储长度
#define FIFO_LIGHT_INT64_T   (FIFO_LIGHT_UINT8_T>>3)  //FIFO存储长度
#define FIFO_LIGHT_DOUBLE    (FIFO_LIGHT_UINT8_T>>3)  //FIFO存储长度

union UNION_UINT8
{
  uint8_t  u_8     [FIFO_LIGHT_UINT8_T];
	uint8_t  u_u8    [FIFO_LIGHT_UINT8_T];
  uint16_t u_u16   [FIFO_LIGHT_UINT16_T];
	int16_t  u_16    [FIFO_LIGHT_INT16_T];
	uint32_t u_u32   [FIFO_LIGHT_UINT32_T];
  int32_t  u_32    [FIFO_LIGHT_INT32_T];
  float    u_float [FIFO_LIGHT_FLOAT];
	uint64_t u_u64   [FIFO_LIGHT_UINT64_T];
	int64_t  u_64    [FIFO_LIGHT_INT64_T];
	double   u_double[FIFO_LIGHT_DOUBLE];
};

typedef struct
{
	bool apply_enable;
  uint32_t start_data;//申请的空间存储的起始地址
	uint32_t end_data;  //申请的空间存储的结束地址
	uint32_t fifo_light;//申请出的fifo长度（单位为可存储申请类型的数量）
	uint32_t rema_light;//剩余fifo空间
	uint32_t cur_piont;//结束指针
	uint32_t end_piont;//开始指针
}TYPE_FIFO_DATA;

extern union UNION_UINT8 g_myunion;
extern TYPE_FIFO_DATA g_fifo_data[FIFO_NABER];

void fifo_init(void);//初始化fifo
bool fifo_apply(uint32_t *fifo_naber,uint32_t datalight,uint32_t light);//申请fifo
uint32_t fifo_remalight(uint32_t fifo_naber);   //读取fif0剩余空间
uint32_t fifo_indata_light(uint32_t fifo_naber);//读取FIFO已经存入的数据数量
bool fifo_clear(uint32_t fifo_naber);//清空fifo

bool fifo_goint_uint8_t (uint32_t fifo_naber,uint8_t  *indata,uint32_t light);
bool fifo_goint_int8_t  (uint32_t fifo_naber,int8_t   *indata,uint32_t light);
bool fifo_goint_uint16_t(uint32_t fifo_naber,uint16_t *indata,uint32_t light);
bool fifo_goint_int16_t (uint32_t fifo_naber,int16_t  *indata,uint32_t light);
bool fifo_goint_uint32_t(uint32_t fifo_naber,uint32_t *indata,uint32_t light);
bool fifo_goint_int32_t (uint32_t fifo_naber,int32_t  *indata,uint32_t ligh);
bool fifo_goint_float   (uint32_t fifo_naber,float    *indata,uint32_t light);
bool fifo_goint_uint64_t(uint32_t fifo_naber,uint64_t *indata,uint32_t light);
bool fifo_goint_int64_t (uint32_t fifo_naber,int64_t  *indata,uint32_t light);
bool fifo_goint_double  (uint32_t fifo_naber,double   *indata,uint32_t light);

bool fifo_read_uint8_t (uint32_t fifo_naber,uint8_t  *indata,uint32_t light);
bool fifo_read_int8_t  (uint32_t fifo_naber,int8_t   *indata,uint32_t light);
bool fifo_read_uint16_t(uint32_t fifo_naber,uint16_t *indata,uint32_t light);
bool fifo_read_int16_t (uint32_t fifo_naber,int16_t  *indata,uint32_t light);
bool fifo_read_uint32_t(uint32_t fifo_naber,uint32_t *indata,uint32_t light);
bool fifo_read_int32_t (uint32_t fifo_naber,int32_t  *indata,uint32_t light);
bool fifo_read_float   (uint32_t fifo_naber,float    *indata,uint32_t light);
bool fifo_read_uint64_t(uint32_t fifo_naber,uint64_t *indata,uint32_t light);
bool fifo_read_int64_t (uint32_t fifo_naber,int64_t  *indata,uint32_t light);
bool fifo_read_double  (uint32_t fifo_naber,double   *indata,uint32_t light);

#endif








