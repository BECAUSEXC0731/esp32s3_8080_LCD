import cv2
import os
import sys


def video_to_images(video_path, output_dir, interval_sec=1, img_format="jpg", quality=95):
    """
    将视频按固定时间间隔切片为图片

    :param video_path:   ★ 视频文件路径（替换为你的视频路径）
    :param output_dir:   ★ 图片输出目录（替换为你想保存的文件夹路径）
    :param interval_sec: 每隔多少秒截取一张图片（默认1秒）
    :param img_format:   图片格式，支持 jpg / png / bmp
    :param quality:      JPEG质量(1-100)，仅对jpg生效；png时为压缩级别(0-9)
    """
    # ==================== 参数校验 ====================
    if not os.path.isfile(video_path):
        print(f"[错误] 视频文件不存在: {video_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # ==================== 打开视频 ====================
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[错误] 无法打开视频: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    frame_interval = max(1, int(fps * interval_sec))

    print("=" * 50)
    print(f"  视频路径  : {video_path}")
    print(f"  输出目录  : {output_dir}")
    print(f"  FPS       : {fps:.2f}")
    print(f"  总帧数    : {total_frames}")
    print(f"  视频时长  : {duration:.2f} 秒")
    print(f"  截取间隔  : 每 {interval_sec} 秒 (即每 {frame_interval} 帧)")
    print("=" * 50)

    # ==================== 逐帧读取并保存 ====================
    frame_idx = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            filename = f"frame_{saved_count:06d}.{img_format}"
            filepath = os.path.join(output_dir, filename)

            # 根据格式设置保存参数
            if img_format.lower() == "jpg":
                params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            elif img_format.lower() == "png":
                params = [cv2.IMWRITE_PNG_COMPRESSION, min(9, max(0, 9 - quality // 11))]
            else:
                params = []

            cv2.imwrite(filepath, frame, params)
            saved_count += 1

            # 打印进度
            progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0
            print(f"\r  进度: {progress:5.1f}% | 已保存: {saved_count} 张", end="", flush=True)

        frame_idx += 1

    cap.release()
    print(f"\n\n[完成] 共处理 {frame_idx} 帧，成功保存 {saved_count} 张图片到:")
    print(f"       {os.path.abspath(output_dir)}")


# =====================================================================
#                        ★ 在下面修改你的配置 ★
# =====================================================================
if __name__ == "__main__":

    VIDEO_PATH   = r"C:/Users/xc/Desktop/yuexin/video/yuexin.mp4"          # ★ 替换为你的视频文件路径
    OUTPUT_DIR   = r"C:/Users/xc/Desktop/yuexin/images/gif"      # ★ 替换为图片输出文件夹路径
    INTERVAL_SEC = 0.04                       # ★ 每隔几秒截一张图（如 0.5 = 每半秒一张）
    IMG_FORMAT   = "jpg"                   # ★ 图片格式: jpg / png / bmp
    QUALITY      = 50                      # ★ JPEG质量(1-100)，越高越清晰、文件越大

    video_to_images(
        video_path=VIDEO_PATH,
        output_dir=OUTPUT_DIR,
        interval_sec=INTERVAL_SEC,
        img_format=IMG_FORMAT,
        quality=QUALITY,
    )