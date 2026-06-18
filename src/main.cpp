/**
 * ILI9341 快速轮播 — 预载PSRAM + LUT寄存器直写
 * 30ms间隔切换
 */
#include <Arduino.h>
#include "images/images.h"

#define CS  10
#define DC  9
#define WR  12
#define RST 8
#define BL  2

const uint8_t DB[16] = {4,5,6,7, 14,15,16,17, 18,21,1,11, 13,40,41,42};

#define REG_W1TS  (*(volatile uint32_t*)0x60004008)
#define REG_W1TC  (*(volatile uint32_t*)0x6000400C)
#define REG1_W1TS (*(volatile uint32_t*)0x60004014)
#define REG1_W1TC (*(volatile uint32_t*)0x60004018)

static uint32_t lo_lut[256], hi_lut[256], hi1_lut[256];
static uint32_t db_mask, db1_mask;

void setBus(uint16_t d){for(int i=0;i<16;i++) digitalWrite(DB[i],(d>>i)&1);}
inline uint16_t sw(uint16_t v){return (v>>8)|(v<<8);}

void buildLUT(){
    db_mask=0;db1_mask=0;
    for(int i=0;i<16;i++){
        if(DB[i]<32) db_mask|=(1UL<<DB[i]);
        else         db1_mask|=(1UL<<(DB[i]-32));
    }
    for(int v=0;v<256;v++){
        uint32_t lo=0,hi=0,hi1=0;
        for(int i=0;i<8;i++){
            if((v>>i)&1){
                if(DB[i]<32) lo|=(1UL<<DB[i]);
                else         hi1|=(1UL<<(DB[i]-32));
            }
        }
        lo_lut[v]=lo;
        for(int i=0;i<8;i++){
            if((v>>i)&1){
                if(DB[i+8]<32) hi|=(1UL<<DB[i+8]);
                else           hi1|=(1UL<<(DB[i+8]-32));
            }
        }
        hi_lut[v]=hi; hi1_lut[v]=hi1;
    }
}

void writeCmd(uint8_t c){digitalWrite(DC,LOW);digitalWrite(CS,LOW);setBus(c);delayMicroseconds(30);digitalWrite(WR,LOW);delayMicroseconds(30);digitalWrite(WR,HIGH);delayMicroseconds(30);digitalWrite(CS,HIGH);}
void writeData8(uint8_t d){digitalWrite(DC,HIGH);digitalWrite(CS,LOW);setBus(d);delayMicroseconds(30);digitalWrite(WR,LOW);delayMicroseconds(30);digitalWrite(WR,HIGH);delayMicroseconds(30);digitalWrite(CS,HIGH);}
void writeData16s(uint16_t d){digitalWrite(DC,HIGH);digitalWrite(CS,LOW);setBus(sw(d));delayMicroseconds(30);digitalWrite(WR,LOW);delayMicroseconds(30);digitalWrite(WR,HIGH);delayMicroseconds(30);digitalWrite(CS,HIGH);}
void setWindow(int x,int y,int w,int h){writeCmd(0x2A);writeData16s(x);writeData16s(x+w-1);writeCmd(0x2B);writeData16s(y);writeData16s(y+h-1);writeCmd(0x2C);}

void initDisplay(){
    pinMode(RST,OUTPUT);digitalWrite(RST,HIGH);delay(10);digitalWrite(RST,LOW);delay(20);digitalWrite(RST,HIGH);delay(120);
    writeCmd(0x01);delay(120);writeCmd(0x11);delay(120);
    writeCmd(0x3A);writeData8(0x55);writeCmd(0x36);writeData8(0x48);
    writeCmd(0xB1);writeData8(0x00);writeData8(0x1B);
    writeCmd(0xC0);writeData8(0x23);writeCmd(0xC1);writeData8(0x10);
    writeCmd(0xC5);writeData8(0x2B);writeData8(0x2B);writeCmd(0xC7);writeData8(0xC0);
    writeCmd(0xB7);writeData8(0x07);writeCmd(0xB6);writeData8(0x0A);writeData8(0xA2);
    writeCmd(0x26);writeData8(0x01);
    writeCmd(0xE0);writeData8(0x0F);writeData8(0x31);writeData8(0x2B);writeData8(0x0C);writeData8(0x0E);writeData8(0x08);writeData8(0x4E);writeData8(0xF1);writeData8(0x37);writeData8(0x07);writeData8(0x10);writeData8(0x03);writeData8(0x0E);writeData8(0x09);writeData8(0x00);
    writeCmd(0xE1);writeData8(0x00);writeData8(0x0E);writeData8(0x14);writeData8(0x03);writeData8(0x11);writeData8(0x07);writeData8(0x31);writeData8(0xC1);writeData8(0x48);writeData8(0x08);writeData8(0x0F);writeData8(0x0C);writeData8(0x31);writeData8(0x36);writeData8(0x0F);
    writeCmd(0x29);delay(50);
}

uint16_t* imgBufs[40];
int curImg=0;

// 快速刷图：LUT总线 + 寄存器WR
void fastPush(uint16_t* buf){
    setWindow(0,0,240,320);
    REG_W1TS=(1UL<<DC);
    REG_W1TC=(1UL<<CS);
    for(int i=0;i<76800;i++){
        uint16_t c=buf[i];
        uint8_t lo=c&0xFF,hi=c>>8;
        uint32_t out=lo_lut[lo]|hi_lut[hi];
        uint32_t out1=hi1_lut[hi];
        if(db_mask){REG_W1TC=db_mask;REG_W1TS=out;}
        if(db1_mask){REG1_W1TC=db1_mask;REG1_W1TS=out1;}
        // WR脉冲: 寄存器写 + NOP满足15ns
        REG_W1TC=(1UL<<WR);asm volatile("nop;nop;nop;nop");
        REG_W1TS=(1UL<<WR);asm volatile("nop;nop;nop;nop");
    }
    REG_W1TS=(1UL<<CS);
}

void setup(){
    Serial.begin(115200);delay(200);
    pinMode(CS,OUTPUT);digitalWrite(CS,HIGH);
    pinMode(DC,OUTPUT);digitalWrite(DC,HIGH);
    pinMode(WR,OUTPUT);digitalWrite(WR,HIGH);
    pinMode(BL,OUTPUT);digitalWrite(BL,HIGH);
    for(int i=0;i<16;i++){pinMode(DB[i],OUTPUT);digitalWrite(DB[i],LOW);}

    buildLUT();
    initDisplay();
    Serial.println("[INIT] OK");

    // 预加载所有图片到PSRAM
    if(IMAGE_COUNT>0){
        int n=IMAGE_COUNT<40?IMAGE_COUNT:40;
        for(int j=0;j<n;j++){
            imgBufs[j]=(uint16_t*)ps_malloc(240*320*2);
            if(!imgBufs[j]) imgBufs[j]=(uint16_t*)heap_caps_malloc(240*320*2,MALLOC_CAP_SPIRAM);
            if(!imgBufs[j]) imgBufs[j]=(uint16_t*)malloc(240*320*2);
            const uint16_t* src=images_list[j];
            for(int i=0;i<76800;i++){
                uint16_t pixel=src[i];
                asm volatile("":::"memory");
                imgBufs[j][i]=pixel;
                if((i&0x1FF)==0) delayMicroseconds(50);
            }
            Serial.printf("[LOAD] %d/%d %p\n",j+1,n,imgBufs[j]);
        }
    }
    Serial.println("[READY]");
}

void loop(){
    static unsigned long lastSwitch=0;
    unsigned long now=millis();
    const unsigned long INTERVAL=30;
    int n=IMAGE_COUNT<40?IMAGE_COUNT:40;

    if(n>0 && now-lastSwitch>=INTERVAL){
        lastSwitch=now;
        fastPush(imgBufs[curImg]);
        curImg=(curImg+1)%n;
    }
}
