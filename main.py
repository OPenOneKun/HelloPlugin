from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import requests
from bs4 import BeautifulSoup
import re
from PIL import Image, ImageDraw, ImageFont
import io
import os

@register(name="SteamHotSales", description="获取Steam热销榜单(图片版)", version="0.2", author="Assistant")
class SteamHotSalesPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 设置字体路径，需要替换为实际的字体文件路径
        self.font_path = "/app/plugins/SteamHotSales/fonts/font.ttf"  # 微软雅黑字体
        self.ensure_font_exists()

    def ensure_font_exists(self):
        """确保字体文件存在"""
        font_dir = "/app/plugins/SteamHotSales/fonts"
        if not os.path.exists(font_dir):
            os.makedirs(font_dir)
        if not os.path.exists(self.font_path):
            # 如果字体文件不存在，可以从网络下载或提示错误
            self.ap.logger.error("字体文件不存在，请确保字体文件路径正确")

    async def initialize(self):
        pass

    def get_steam_top_sellers(self):
        try:
            url = "https://store.steampowered.com/search/?filter=topsellers"
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            games = []
            # 获取前10个热销游戏
            for game in soup.select('#search_resultsRows a')[:10]:
                title = game.select_one('.title').text.strip()
                price = game.select_one('.search_price').text.strip()
                price = re.sub(r'\s+', ' ', price)
                if not price:
                    price = "价格未知"
                
                games.append((title, price))
            
            return games
        except Exception as e:
            return None

    def create_image(self, games):
        """创建图片"""
        # 设置图片尺寸和颜色
        width = 800
        height = 600
        background_color = (40, 44, 52)  # 深色背景
        text_color = (255, 255, 255)  # 白色文字
        
        # 创建图片和绘图对象
        image = Image.new('RGB', (width, height), background_color)
        draw = ImageDraw.Draw(image)
        
        # 设置字体
        title_font = ImageFont.truetype(self.font_path, 36)
        game_font = ImageFont.truetype(self.font_path, 24)
        
        # 绘制标题
        title = "Steam 热销榜 TOP 10"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 30), title, font=title_font, fill=text_color)
        
        # 绘制游戏列表
        y = 100
        for i, (game_name, price) in enumerate(games, 1):
            text = f"{i}. {game_name}"
            draw.text((40, y), text, font=game_font, fill=text_color)
            draw.text((40, y+30), f"   价格: {price}", font=game_font, fill=(135, 206, 235))  # 浅蓝色价格
            y += 80
            
        # 绘制时间
        from datetime import datetime
        time_text = f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        time_font = ImageFont.truetype(self.font_path, 16)
        draw.text((20, height-30), time_text, font=time_font, fill=(160, 160, 160))
        
        # 转换图片为字节流
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr

    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message.lower()
        if msg in ["steam", "steam热销", "steam热销榜"]:
            self.ap.logger.debug(f"正在获取Steam热销榜 - 请求来自: {ctx.event.sender_id}")
            games = self.get_steam_top_sellers()
            
            if games:
                # 生成图片
                img_bytes = self.create_image(games)
                # 添加图片回复
                ctx.add_return("image", [img_bytes])
            else:
                ctx.add_return("reply", ["获取Steam热销榜失败，请稍后再试"])
            
            ctx.prevent_default()

    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message.lower()
        if msg in ["steam", "steam热销", "steam热销榜"]:
            self.ap.logger.debug(f"正在获取Steam热销榜 - 请求来自群: {ctx.event.group_id}")
            games = self.get_steam_top_sellers()
            
            if games:
                # 生成图片
                img_bytes = self.create_image(games)
                # 添加图片回复
                ctx.add_return("image", [img_bytes])
            else:
                ctx.add_return("reply", ["获取Steam热销榜失败，请稍后再试"])
            
            ctx.prevent_default()

    def __del__(self):
        pass
