This is a library to allow communicating to a Midea AC via the Local area network.

# midea-msmart
[![Build Status](https://travis-ci.org/mac-zhou/midea-msmart.svg?branch=master)](https://travis-ci.org/mac-zhou/midea-msmart)
[![PyPI](https://img.shields.io/pypi/v/msmart.svg?maxAge=3600)](https://pypi.org/project/msmart/)


This a mirror from the repo at [NeoAcheron/midea-ac-py](https://github.com/NeoAcheron/midea-ac-py).

But this library just allow communicating to a Midea AC via the Local area network, not via the Midea Cloud yet.

Thanks for [yitsushi's project](https://github.com/yitsushi/midea-air-condition), [NeoAcheron's project](https://github.com/NeoAcheron/midea-ac-py), [andersonshatch's project](https://github.com/andersonshatch/midea-ac-py).

## How to Use
- you can use command ```midea-discover``` to discover midea devices on the host in the same Local area network. Note: This component only supports devices with model 0xac (air conditioner) and words ```supported``` in the output.
    ```shell
    pip3 install msmart
    midea-discover
    ```
- then you can use a custom component for Home Assistant [here](https://github.com/mac-zhou/midea-ac-py)

## Buy me a cup of coffee to help maintain this project further?

- [via Paypal](https://www.paypal.me/himaczhou)
- [via Bitcoin](bitcoin:3GAvud4ZcppF5xeTPEqF9FcX2buvTsi2Hy) (**3GAvud4ZcppF5xeTPEqF9FcX2buvTsi2Hy**)
- [via AliPay(支付宝)](https://i.loli.net/2020/05/08/nNSTAPUGDgX2sBe.png)
- [via WeChatPay(微信)](https://i.loli.net/2020/05/08/ouj6SdnVirDzRw9.jpg)

Your donation will make me work better for this project.