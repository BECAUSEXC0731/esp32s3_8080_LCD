# ILI9341 8080 并行驱动踩坑全记录

## 最终状态：✅ 完全正常

全屏红/绿/蓝/白/黑纯色显示正常，图片循环播放基础已打通。

---

## 失败历程及根因分析

### 坑1：TFT_eSPI 库崩溃（StoreProhibited）

**现象**：`tft.begin()` 时 `StoreProhibited`，`EXCVADDR=0x10`

**根因**：TFT_eSPI v2.5.43 与 Arduino ESP32 3.x 框架不兼容。ESP32-S3 上 PSRAM OPI 初始化后，TFT_eSPI 的 `SPIClass(VSPI)` 构造失败，导致空指针解引用。

**解决**：放弃 TFT_eSPI，手写 8080 并行驱动。

---

### 坑2：SPI 模式不工作

**现象**：SPI 初始化不崩溃，但屏幕始终白色

**根因**：正点原子 ILI9341 模组默认硬件配置为 **8080 16 位并行模式**，IM[3:0] 引脚通过板载电阻固定，无法切换到 SPI 模式。SPI 引脚虽引出但 ILI9341 内部忽略 SPI 信号。

**解决**：改用 8080 并行接口（需 16 根数据线 + 5 根控制线）。

---

### 坑3：REG_WRITE 触发 spinlock 崩溃

**现象**：`fillScreen()` 中 `spinlock_acquire` 断言失败 `result == core_id || result == SPINLOCK_FREE`

**根因**：ESP32-S3 双核架构下，`REG_WRITE` 宏内部使用 spinlock 保护总线访问。当 Core 1 执行 GPIO 写操作时，Core 0 可能正持有 PSRAM/Flash 总线锁，导致 spinlock 获取失败。`qio_opi` PSRAM 模式下此问题更频繁。

**解决**：绕过 `REG_WRITE`，直接使用 `*(volatile uint32_t*)0x60004xxx` 指针访问 GPIO 寄存器。

---

### 坑4：WR 脉冲时序不足

**现象**：屏幕始终白色，8080 命令未生效

**根因**：ILI9341 8080 写时序要求 WR 低脉冲宽度 ≥ 15ns。初期代码使用 `REG_WRITE` 或直接寄存器写的 WR 脉冲仅 ~8ns（2 条指令 @240MHz），不满足最小脉宽。

**解决**：在 WR 脉冲前后加入 `delayMicroseconds(30-50)` 延时，给总线充足的建立和保持时间。

---

### 坑5：数据总线高低字节映射问题 ⭐ 核心

**现象**：
- 全屏填充只有屏幕边缘一条细线
- 颜色正常，但窗口大小/位置完全错误
- `fillRect(95, 135, 50, 50)` 只显示微小色块

**根因**：正点原子模组的 D0-D15 丝印与 ILI9341 数据总线 D[1:17] 的对应关系导致 **16 位命令参数的字节序反转**：

```
我们的 D[0:7]  ←→  ILI9341 的 D[17:10]（高字节）
我们的 D[8:15] ←→  ILI9341 的 D[8:1]  （低字节）
```

对于 16 位地址参数（如 CASET 的 `0x00EF`=239）：
- 写入 `0x00EF` → ILI9341 收到高字节 `0xEF`、低字节 `0x00`
- ILI9341 解析为 `0xEF00` = 61184 → 远超屏幕范围（0-239）

但 0x0000（黑色）是对称值，交换后仍为 `0x0000`，所以黑色填充始终正常。

**解决**：16 位地址参数（CASET/PASET 的 x, y, w, h）写入前做 `swap16()` 字节交换；像素颜色数据不交换。

---

### 坑6：GPIO 8 与 PSRAM 冲突

**现象**：手动复位 `digitalWrite(8, LOW)` 导致 StoreProhibited

**根因**：ESP32-S3-WROOM-1 N16R8 模组中 GPIO 8 参与 OPI PSRAM 的 D4 数据线。手动拉低 GPIO 8 会中断 PSRAM 通信，触发总线异常。

**解决**：不手动复位 GPIO 8，让 ILI9341 初始化序列中的软件复位命令（0x01）处理。

---

### 坑7：RD 引脚悬空干扰

**现象**：8080 通信不稳定

**根因**：LCD Pin 4（RD，读使能）悬空时，电磁干扰可能触发伪读操作，干扰写时序。

**解决**：将 RD（LCD Pin 4）接 3.3V 拉高。

---

## 最终配置总结

### 硬件连接

见 `docs/hardware_connection_8080.md`

### 软件关键点

| 项目 | 配置 |
|------|------|
| PSRAM | `qio_opi`（Quad Flash + Octal PSRAM） |
| GPIO 访问 | 直接 `*(volatile uint32_t*)0x60004xxx`，不用 REG_WRITE |
| WR 脉宽 | 30-50μs（硬件最小要求 15ns，留足余量） |
| 数据总线 | 地址参数 swap16()，像素颜色不 swap |
| RD 引脚 | 接 3.3V |
| GPIO 8 | 不用做 GPIO 输出（PSRAM 占用） |

### 数据总线字节模型

```
软件侧 16-bit 值: [bit15..bit8] [bit7..bit0]
                      ↓              ↓
ESP32 GPIO:        D[8:15]        D[0:7]
                      ↓              ↓
ILI934I 总线:      D[8:1]        D[17:10]   ← 字节交叉！
                      ↓              ↓
ILI934I 解析:      低字节         高字节
```

因此地址参数需在软件侧 `swap16()`，像素颜色无需（RGB565 位域恰好自洽）。
