# Untitled - By: PanZhaoHui - Tue May 13 2025

import sensor
import time
import image
import display
from pyb import UART

uart = UART(3, 9600)  # 波特率为9600
sensor.reset()
sensor.set_vflip(False)
sensor.set_hmirror(False)
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQVGA)  # 160x120分辨率
sensor.skip_frames(time=2000)

lcd = display.SPIDisplay()
clock = time.clock()

# 阈值设置
THRESHOLD = (0, 30, -128, 127, -128, 127)

# ROI设置 - 聚焦图像中央区域
ROI_WIDTH = 120    # ROI宽度
ROI_HEIGHT = 80    # ROI高度
ROI_X = (160 - ROI_WIDTH) // 2  # 水平居中
ROI_Y = (120 - ROI_HEIGHT) // 2  # 垂直居中

# 横线检测参数
HORIZONTAL_LINE_THRESHOLD = 1000  # 横线检测的阈值
MIN_HORIZONTAL_LINE_LENGTH = 40   # 最小横线长度（适应ROI）
HORIZONTAL_ANGLE_TOLERANCE = 15   # 水平角度容差

# 循迹参数
CENTER_TOLERANCE = 8  # 中心容差范围（像素）
TURN_SENSITIVITY = 20  # 转向灵敏度

# 频繁转向检测参数
TURN_HISTORY_SIZE = 20            # 记录历史转向的帧数
LEFT_TURN_THRESHOLD = 20           # 在历史记录中左转次数阈值
RIGHT_TURN_THRESHOLD = 20          # 在历史记录中右转次数阈值
turn_history = []                 # 存储最近的转向记录
last_command = 'n'                # 记录上一次发送的命令

def get_endpoint(line):
    (x1, y1, x2, y2) = line.line()
    # 返回最下方的点（距离摄像头最近的点）
    if y1 > y2:
        return (x1, y1)
    else:
        return (x2, y2)

def theta_change(theta):
    if theta > 90:
        theta = theta - 180
        return theta
    else:
        return theta

def is_horizontal_line(line):
    """
    准确判断是否为水平线
    """
    (x1, y1, x2, y2) = line.line()

    # 计算线段的角度（相对于水平方向）
    dx = x2 - x1
    dy = y2 - y1

    # 避免除以零
    if dx == 0:
        angle = 90
    else:
        angle = abs(math.degrees(math.atan2(dy, dx)))

    # 水平线的角度应该在0°附近或180°附近
    # 使用更严格的角度判断
    is_horizontal = (angle <= HORIZONTAL_ANGLE_TOLERANCE) or (angle >= 180 - HORIZONTAL_ANGLE_TOLERANCE)

    # 检查线段长度
    is_long_enough = line.length() >= MIN_HORIZONTAL_LINE_LENGTH

    # 检查线段是否接近水平（y坐标变化很小）
    y_variation = abs(y1 - y2)
    is_y_stable = y_variation < 5  # y坐标变化很小

    return is_horizontal and is_long_enough and is_y_stable

def detect_horizontal_line_robust(img):
    """
    更鲁棒的横线检测方法 - 在ROI区域内检测
    """
    # 在ROI区域内检测横线
    roi = (ROI_X, ROI_Y, ROI_WIDTH, ROI_HEIGHT)

    # 方法1: 使用线段检测
    lines = img.find_line_segments(roi=roi, threshold=HORIZONTAL_LINE_THRESHOLD, theta_margin=25, rho_margin=25)

    horizontal_lines = []
    for line in lines:g
        if is_horizontal_line(line):
            horizontal_lines.append(line)
            # 在图像上绘制检测到的横线（绿色）
            img.draw_line(line.line(), color=(0, 255, 0), thickness=3)

    # 方法2: 使用行像素统计（备用方法）- 在ROI底部区域检测
    if not horizontal_lines:
        # 在ROI底部区域检测横线
        roi_height = 15
        roi_y = ROI_Y + ROI_HEIGHT - roi_height - 5
        horizontal_roi = (ROI_X, roi_y, ROI_WIDTH, roi_height)

        # 统计ROI区域内的白色像素（二值化后黑线变白）
        stats = img.get_statistics(roi=horizontal_roi)
        white_pixels = stats.l_mean()  # 亮度均值

        # 如果白色像素足够多，说明有横线
        if white_pixels > 100:  # 调整这个阈值
            # 在ROI区域绘制矩形（蓝色）
            img.draw_rectangle(horizontal_roi, color=(0, 0, 255), thickness=2)
            return True

    return len(horizontal_lines) > 0

def update_turn_history(command):
    """
    更新转向历史记录
    """
    global turn_history

    # 只记录转向命令，忽略直行、停止和横线命令
    if command in ['l', 'r']:
        turn_history.append(command)

        # 保持历史记录长度不超过设定大小
        if len(turn_history) > TURN_HISTORY_SIZE:
            turn_history.pop(0)

def check_frequent_left_turns():
    """
    检查是否频繁左转
    """
    global turn_history

    if len(turn_history) < LEFT_TURN_THRESHOLD:
        return False

    # 统计最近记录中的左转次数
    left_count = turn_history.count('l')

    # 如果左转次数超过阈值，则认为是频繁左转
    if left_count >= LEFT_TURN_THRESHOLD:
        # 重置历史记录，避免连续发送'b'
        turn_history = []
        return True

    return False

def check_frequent_right_turns():
    """
    检查是否频繁右转
    """
    global turn_history

    if len(turn_history) < RIGHT_TURN_THRESHOLD:
        return False

    # 统计最近记录中的右转次数
    right_count = turn_history.count('r')

    # 如果右转次数超过阈值，则认为是频繁右转
    if right_count >= RIGHT_TURN_THRESHOLD:
        # 重置历史记录，避免连续发送'c'
        turn_history = []
        return True

    return False

# 添加数学库支持
import math

while True:
    clock.tick()
    img = sensor.snapshot()

    # 在图像上绘制ROI区域（黄色边框）
    img.draw_rectangle(ROI_X, ROI_Y, ROI_WIDTH, ROI_HEIGHT, color=(255, 255, 0), thickness=2)

    # 绘制中心线（红色）
    center_x = ROI_X + ROI_WIDTH // 2
    img.draw_line(center_x, ROI_Y, center_x, ROI_Y + ROI_HEIGHT, color=(255, 0, 0), thickness=1)

    # 绘制中心容差区域（绿色）
    left_boundary = center_x - CENTER_TOLERANCE
    right_boundary = center_x + CENTER_TOLERANCE
    img.draw_line(left_boundary, ROI_Y, left_boundary, ROI_Y + ROI_HEIGHT, color=(0, 255, 0), thickness=1)
    img.draw_line(right_boundary, ROI_Y, right_boundary, ROI_Y + ROI_HEIGHT, color=(0, 255, 0), thickness=1)

    # 图像预处理 - 对整个图像进行处理
    img.binary([THRESHOLD])
    img.open(1)
    img.gaussian(1)

    current_command = 'n'  # 当前帧的决定命令

    # 首先检测横线（优先处理）
    if detect_horizontal_line_robust(img):
        current_command = 'T'  # 发送横线检测信号
        print("检测到横线，发送 T")
    else:
        # 如果没有检测到横线，则进行正常的循迹检测 - 在ROI区域内检测
        line = img.get_regression([(100, 100)], roi=(ROI_X, ROI_Y, ROI_WIDTH, ROI_HEIGHT), robust=True)

        if line and line.magnitude() > 8:
            img.draw_line(line.line(), color=(255, 0, 0), thickness=2)
            bottom_x, bottom_y = get_endpoint(line)

            # 在图像上标记底部端点
            img.draw_circle(int(bottom_x), int(bottom_y), 3, color=(255, 0, 0), thickness=2)

            # 计算相对于ROI中心的误差
            roi_center_x = ROI_X + ROI_WIDTH // 2
            error_x = bottom_x - roi_center_x
            theta = theta_change(line.theta())

            # 显示误差和角度信息
            img.draw_string(5, 5, f"Error: {error_x:.1f}", color=(255, 255, 255), scale=1)
            img.draw_string(5, 15, f"Theta: {theta:.1f}", color=(255, 255, 255), scale=1)

            # 修改循迹控制逻辑：基于位置误差判断转向
            if error_x > CENTER_TOLERANCE:
                # 黑线在右侧，需要右转让线回到中心
                current_command = 'r'
                print(f"黑线在右侧(误差:{error_x:.1f})，右转")
            elif error_x < -CENTER_TOLERANCE:
                # 黑线在左侧，需要左转让线回到中心
                current_command = 'l'
                print(f"黑线在左侧(误差:{error_x:.1f})，左转")
            else:
                # 黑线在中心区域，直行
                current_command = 'f'
                print(f"黑线在中心(误差:{error_x:.1f})，直行")
        else:
            current_command = 'n'
            print("未检测到路径")

    # 更新转向历史记录
    update_turn_history(current_command)

    # 检查是否频繁左转或频繁右转
    if check_frequent_left_turns():
        uart.write('b')
        print("频繁左转，发送 b")
        # 在图像上显示频繁左转警告
        img.draw_string(10, 10, "FREQUENT LEFT TURNS!", color=(255, 0, 0), scale=2)
    elif check_frequent_right_turns():
        uart.write('c')
        print("频繁右转，发送 c")
        # 在图像上显示频繁右转警告
        img.draw_string(10, 10, "FREQUENT RIGHT TURNS!", color=(0, 0, 255), scale=2)
    else:
        # 如果没有频繁转向，发送正常的命令
        uart.write(current_command)

    last_command = current_command

    # 在图像上显示ROI信息
    img.draw_string(ROI_X, ROI_Y - 15, "ROI Area", color=(255, 255, 0), scale=1)

    print("FPS:", clock.fps())
    print("转向历史:", turn_history)
    lcd.write(img)  # 显示图像
