# rstbot

# Install

`pip install rstbot -i https://pypi.org/simple -U`

# Example

```python
from rstbot import WeChat, WeChatMsg

wechat = WeChat(url="http://127.0.0.1:8898/", logger=True)


@wechat.on_msg
def msg(ctx: WeChatMsg):
    if ctx.FromUserName == ctx.CurrentWxid:
        return
    if ctx.Content == 'test':
        wechat.sendMsg(ctx.FromUserName, 'Test successfully!')


wechat.run()
```

# License

MIT
