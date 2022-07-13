#!/data/data/com.termux/files/usr/bin/python
from msmart.device import air_conditioning as ac
from msmart.device.base import device
import logging
import time
import sys
import argparse

logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)

# first take device's ip and id, port is generally 6444
# pip3 install msmart; midea-discover
device = ac('YOUR_AC_IP', int('YOUR_AC_ID'), 6444)
# If the device is using protocol 3 (aka 8370)
# you must authenticate with device's k1 and token.
# adb logcat | grep doKeyAgree
device.authenticate('YOUR_AC_K1', 'YOUR_AC_TOKEN')

def p():
    print({
        'id': device.id,
        'name': device.ip,
        'power_state': device.power_state,
        'prompt_tone': device.prompt_tone,
        'target_temperature': device.target_temperature,
        'operational_mode': device.operational_mode,
        'fan_speed': device.fan_speed,
        'swing_mode': device.swing_mode,
        'eco_mode': device.eco_mode,
        'turbo_mode': device.turbo_mode,
        'indoor_temperature': device.indoor_temperature,
        'outdoor_temperature': device.outdoor_temperature,
        'off_timer': device.off_timer,
        'on_timer': device.on_timer,
    })

# Refresh the object with the actual state by querying it
def show():
    device.refresh()
    p()

def cmd():
    args = argparse.ArgumentParser(description = u'美的空调设置')
    group = args.add_mutually_exclusive_group()
    group.add_argument("--O", action="store_true", help = u"开机")
    group.add_argument("--o", action="store_true", help = u"关机")
    group = args.add_mutually_exclusive_group()
    group.add_argument("--P", action="store_true", help = "开关屏显")
    args.add_argument("-m", "--mode", type = int, help = u"模式:1 自动，2 制冷，3 抽湿，4 制热，5 送风", choices=list(map(lambda c: c.value, ac.operational_mode_enum)))
    args.add_argument("-t", "--temp", type = int, help = u"温度: 24,25,26", choices=[24,25,26])
    args.add_argument('-f',"--fan", type = int, help = u'风速', choices=list(map(lambda c: c.value, ac.fan_speed_enum)))
    args.add_argument('-s',"--swing", type = int, help = u'摆风: 0 关闭，12 垂直，3 水平，15 垂直+水平', choices=list(map(lambda c: c.value, ac.swing_mode_enum)))
    args.add_argument("-o", "--off_timer", type = str, help = u"定时关机(时:分，31:45-32:00 关定时，0:0 关机)", choices=list(map(lambda i: r'{}:{}'.format(i // 60, i % 60),range(2 ** 5 * 60 + 1))))
    args.add_argument("-O", "--on_timer", type = str, help = u"定时开机(时:分，32:45-32:00 关定时，0:0 开机)", choices=list(map(lambda i: r'{}:{}'.format(i // 60, i % 60),range(2 ** 5 * 60 + 1))))
    args = args.parse_args()

    n = 0
    if args.O:
        device.power_state = True
        n += 1
    if args.o:
        device.power_state = False
        n += 1
    if args.P:
        device.prompt_tone = True
        n += 1
    if args.temp:
        device.target_temperature = args.temp
        n += 1
    if args.fan is not None:
        device.fan_speed = ac.fan_speed_enum.get(args.fan)
        n += 1
    if args.swing is not None:
        device.swing_mode= ac.swing_mode_enum.get(args.swing)
        n += 1
    if args.mode:
        device.operational_mode = ac.operational_mode_enum.get(args.mode)
        n += 1
    if args.off_timer:
        device.off_timer = {'status':True, 'time':args.off_timer}
        n += 1
    if args.on_timer:
        device.on_timer = {'status':True, 'time':args.on_timer}
        n += 1

    if n > 0:
        time.sleep(1)
        # commit the changes with apply()
        device.apply()
        p()
        show()

if __name__=="__main__":
    show()
    cmd()
