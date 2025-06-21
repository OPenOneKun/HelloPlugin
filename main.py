from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from pathlib import Path
from typing import Literal
import base64
import ujson
import asyncio
from .prompt import get_prompt

class FuckOrNotPlugin(BasePlugin):
    """AI评分系统，评估图片可操性"""
    
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.config = {
            "base_url": "https://api.laozhang.ai/v1/chat/completions",
            "api_key": "sk-2PEpB0eGEVHy6phV936915Ee3fA341D1A8F273730a25Ae74",
            "model": "gemini-2.5-flash-preview-05-20",
            "withdraw_time": 0
        }
        
    async def initialize(self):
        """加载配置"""
        self.config = self.ap.plugin_config.get(self.name, self.config)
        self.logger.info(f"插件配置已加载: {self.config}")
        
    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        """处理群聊消息"""
        await self._process_message(ctx)
    
    @handler(PersonNormalMessageReceived)
    async def handle_person_message(self, ctx: EventContext):
        """处理私聊消息"""
        await self._process_message(ctx)
    
    async def _process_message(self, ctx: EventContext):
        """处理消息的核心逻辑"""
        # 检查是否包含命令
        if not ctx.event.text_message.startswith("上"):
            return
            
        # 获取消息内容
        msg = ctx.event.text_message.strip()
        event = ctx.event
        bot = self.ap.bot
        
        # 解析模式参数
        mode = "简短模式"
        if "--m" in msg:
            parts = msg.split("--m")
            if len(parts) > 1:
                mode_part = parts[1].strip()
                if mode_part in ["简短模式", "详细模式", "小说模式"]:
                    mode = mode_part
        
        # 获取图片
        image_bytes = None
        if event.image_list:  # 当前消息包含图片
            image_url = event.image_list[0]
            image_bytes = await self._download_image(image_url)
        elif event.reply_to_message_id:  # 回复消息
            reply_msg = await self.ap.get_message_by_id(event.reply_to_message_id)
            if reply_msg and reply_msg.image_list:
                image_bytes = await self._download_image(reply_msg.image_list[0])
        elif "@" in msg:  # @用户
            # 提取用户ID
            user_id = None
            for seg in msg.split():
                if seg.startswith("@") and seg[1:].isdigit():
                    user_id = int(seg[1:])
                    break
            
            if user_id:
                image_bytes = await self._get_qq_avatar(user_id)
        
        if not image_bytes:
            ctx.add_return("reply", ["请提供图片、@用户或回复图片消息"])
            ctx.prevent_default()
            return
        
        try:
            # 获取提示词
            prompt = get_prompt(mode)
            
            # 调用Gemini API
            data = await self._call_gemini_api(prompt, image_bytes)
            
            # 渲染结果
            image = await self._render_result(data)
            
            # 发送结果
            ctx.add_return("reply", [image])
            ctx.prevent_default()
            
            # 设置撤回
            if self.config["withdraw_time"] > 0:
                asyncio.create_task(
                    self._withdraw_message(ctx.event.message_id, self.config["withdraw_time"])
                )
                
        except Exception as e:
            self.logger.error(f"评分失败: {str(e)}")
            ctx.add_return("reply", [f"评分失败: {str(e)}"])
            ctx.prevent_default()
    
    async def _download_image(self, url: str) -> bytes:
        """下载图片"""
        async with self.ap.http_session.get(url) as response:
            response.raise_for_status()
            return await response.read()
    
    async def _get_qq_avatar(self, user_id: int) -> bytes:
        """获取QQ头像"""
        avatar_url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        return await self._download_image(avatar_url)
    
    async def _call_gemini_api(self, prompt: str, image_bytes: bytes) -> dict:
        """调用Gemini API"""
        base_url = self.config["base_url"]
        model = self.config["model"]
        headers = {
            "Authorization": "Bearer sk-2PEpB0eGEVHy6phV936915Ee3fA341D1A8F273730a25Ae74",
            "Content-Type": "application/json"
           }
        payload = {
            "model": model,
            "messages":[{
            "system_instruction": {"parts": [{"text": prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "请分析这张图片并决定：上还是不上？"},
                        {
                            "inline_data": {
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                                "mime_type": "image/jpeg",
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "verdict": {"type": "STRING", "description": "'上' 或 '不上'"},
                        "rating": {"type": "STRING", "description": "1到10的数字"},
                        "explanation": {"type": "STRING", "description": "你的明确、粗俗的解释（中文）"},
                    },
                },
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
            ],

             }
             ]
               
        }
        
        async with self.ap.http_session.post(base_url, json=payload,headers=headers,timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            return self._parse_response(data)
    
    def _parse_response(self, response: dict) -> dict:
        """解析API响应"""
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            return ujson.loads(text)
        except (KeyError, IndexError, ValueError) as e:
            self.logger.error(f"解析响应失败: {response}")
            raise ValueError("API返回格式异常") from e
    
    async def _render_result(self, data: dict) -> str:
        """渲染结果图片"""
        # 这里简化处理，实际应使用HTML模板渲染
        return f"判定: {data['verdict']}\n评分: {data['rating']}/10\n理由: {data['explanation']}"
    
    async def _withdraw_message(self, message_id: int, delay: int):
        """撤回消息"""
        await asyncio.sleep(delay)
        try:
            await self.ap.bot.delete_msg(message_id=message_id)
        except Exception as e:
            self.logger.warning(f"撤回消息失败: {str(e)}")
    
    def __del__(self):
        """插件卸载"""
        pass