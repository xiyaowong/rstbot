# pylint: disable=R0902
"""
Lovely framework for RSTBot.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import copy
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

import httpx
import socketio

default_logger = logging.getLogger("wechat")

TEXT_MSG_TYPE = 1
APP_MSG_TYPE = 49
IMAGE_MSG_TYPE = 3
EMOJI_MSG_TYPE = 47


class WeChatMsg:
    def __init__(self, rawData):
        self.CurrentWxid = rawData["CurrentWxid"]
        self.data = rawData["CurrentPacket"]["Data"]
        self.ActionNickName: str = self.data["ActionNickName"]
        self.ActionUserName: str = self.data["ActionUserName"]
        self.Content: str = self.data["Content"]
        self.CreateTime: int = self.data["CreateTime"]
        self.FromUserName: str = self.data["FromUserName"]
        self.ImgBuf: str = self.data["ImgBuf"]
        self.ImgStatus: int = self.data["ImgStatus"]
        self.MsgId: int = self.data["MsgId"]
        self.MsgSource: str = self.data["MsgSource"]
        self.MsgType: int = self.data["MsgType"]
        self.NewMsgId: int = self.data["NewMsgId"]
        self.PushContent: str = self.data["PushContent"]
        self.Status: int = self.data["Status"]
        self.ToUserName: str = self.data["ToUserName"]


class EventMsg:
    def __init__(self, rawData):
        self.CurrentWxid = rawData["CurrentWxid"]
        self.data = rawData["CurrentPacket"]["Data"]


class WeChat:
    """
    :param url: The URL of the Socket.IO server. It can include custom
                query string parameters if required by the server.
    :param wxid: The wxid of your bot. It must be set if you try to call the API.
                  If it not be set, when receiving the message, it will be
                  set to the CurrentWxid automatically.
    :param logger: To enable logging set to ``True`` or pass a logger object to
                   use. To disable logging set to ``False``. The default is
                   ``False``. Note that fatal errors are logged even when
                   ``logger`` is ``False``.
    """

    def __init__(self, url="http://127.0.0.1:8898", wxid=None, logger=False):
        self.url = url.strip("/")
        self.wxid = wxid

        # for http request
        self._http = httpx.Client(
            base_url=self.url,
            headers={"Content-Type": "application/json"},
            timeout=25,
        )
        self._lock = threading.Lock()

        if not isinstance(logger, bool):
            self.logger = logger
        else:
            self.logger = default_logger
            if not logging.root.handlers and self.logger.level == logging.NOTSET:
                if logger:
                    self.logger.setLevel(logging.INFO)
                else:
                    self.logger.setLevel(logging.ERROR)
                h = logging.StreamHandler()
                h.setFormatter(
                    logging.Formatter("%(asctime)s[%(levelname)s] %(message)s")
                )
                self.logger.addHandler(h)

        # initialize socketio client
        self.sio = socketio.Client(logger=self.logger)
        self.sio.on("OnWeChatMsgs")(self._handle_msg)
        self.sio.on("OnEventMsgs")(self._handle_event)

        self._pool = ThreadPoolExecutor(999)

        self._msg_receivers = []
        self._event_receivers = []

    #####################client begin#######################
    #####################for connection#######################
    def _pool_callback(self, worker):
        worker_exception = worker.exception()
        if worker_exception:
            try:
                raise worker_exception
            except Exception:
                self.logger.error(traceback.format_exc())

    def _pool_submit(self, *args, **kwargs):
        self._pool.submit(*args, **kwargs).add_done_callback(self._pool_callback)

    # add receiver
    def on_msg(self, receiver):
        """Add message receiver"""
        self._msg_receivers.append(receiver)

    def on_event(self, receiver):
        """Add event receiver"""
        self._event_receivers.append(receiver)

    # run receiver
    def _distribute_msg_ctx(self, ctx: WeChatMsg):
        # set self.wxid
        if self.wxid is None:
            self.logger.info("Set wxid to CurrentWxid.")
            self.wxid = ctx.CurrentWxid
        for receiver in self._msg_receivers:
            self._pool_submit(receiver, copy.deepcopy(ctx))

    def _distribute_event_ctx(self, ctx):
        # set self.wxid
        if self.wxid is None:
            self.logger.info("Set wxid to CurrentWxid.")
            self.wxid = ctx.CurrentWxid
        for receiver in self._msg_receivers:
            self._pool_submit(receiver, copy.deepcopy(ctx))

    # receive original data
    def _handle_msg(self, raw):
        self.logger.info(raw)
        self._pool_submit(self._distribute_msg_ctx, WeChatMsg(raw))

    def _handle_event(self, raw):
        self.logger.info(raw)
        self._pool_submit(self._distribute_event_ctx, EventMsg(raw))

    def run(self):
        """Start bot"""
        self.logger.info("Trying to Connect the server...")
        try:
            self.sio.connect(self.url, transports=["websocket"])
        except Exception:
            self.logger.error(traceback.format_exc())
            self.sio.disconnect()
            self._pool.shutdown(False)
        else:
            try:
                self.sio.wait()
            except KeyboardInterrupt:
                pass
            finally:
                print("bye~")
                self.sio.disconnect()
                self._pool.shutdown(False)

    #####################action begin#######################
    #####################for api#######################
    def baseRequest(
        self,
        method: str,
        funcname: str,
        path: str,
        payload: dict = None,
        params: dict = None,
    ) -> dict:
        """Basic request method.
        It returns a dict(when response is JSON format string) or string.
        Return None if request failed.
        """
        if self.wxid is None:
            raise Exception("No wxid set!")

        default_params = {"wxid": self.wxid, "timeout": 20, "funcname": funcname}
        if params is None:
            params = default_params
        else:
            params = params.update(default_params)

        try:
            self._lock.acquire()
            threading.Timer(1.5, self._lock.release).start()
            resp = self._http.request(
                method, httpx.URL(url=path, params=params), json=payload
            )
            resp.raise_for_status()
        except Exception:
            self.logger.error(traceback.format_exc())
        else:
            try:
                res = resp.json()
            except Exception:
                res = resp.text
            return res
        return None

    def post(
        self,
        funcname: str,
        payload: dict,
        params: dict = None,
        path: str = "/v1/LuaApiCaller",
    ) -> dict:
        """Post wrapper"""
        return self.baseRequest(
            "POST", funcname=funcname, path=path, payload=payload, params=params
        )

    def get(
        self,
        funcname: str,
        params: dict = None,
        path: str = "/v1/LuaApiCaller",
    ) -> dict:
        """Get wrapper"""
        return self.baseRequest("GET", funcname=funcname, path=path, params=params)

    def sendMsg(self, toUserName, content, atUsers=""):
        return self.post(
            "SendMsg",
            {
                "ToUserName": toUserName,
                "Content": content,
                "MsgType": TEXT_MSG_TYPE,
                "AtUsers": atUsers,
            },
        )

    def sendAppMsg(self, toUserName, content):
        return self.post(
            "SendAppMsg",
            {
                "ToUserName": toUserName,
                "Content": content,
                "MsgType": APP_MSG_TYPE,
            },
        )

    def sendImage(self, toUserName, imagePath="", imageURL=""):
        payload = {"ToUserName": toUserName}
        assert any([imagePath, imageURL]), "At least one choice!!!"
        if imagePath:
            payload.update({"ImagePath": imagePath})
        else:
            payload.update({"ImageUrl": imageURL})
        return self.post("SendImage", payload)

    def sendVoice(self, toUserName, voicePath="", voiceURL=""):
        payload = {"ToUserName": toUserName}
        assert any([voicePath, voiceURL]), "At least one choice!!!"
        if voicePath:
            payload.update({"VoicePath": voicePath})
        else:
            payload.update({"VoiceUrl": voiceURL})
        return self.post("SendVoice", payload)

    def sendEmoji(self, toUserName, emojiMD5):
        return self.post("SendEmoji", {"ToUserName": toUserName, "EmojiMd5": emojiMD5})
