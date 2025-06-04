from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
from io import BytesIO
import os
import textwrap

@register(name="SteamHotSales", description="获取Steam热销榜单(图片版)", version="0.4", author="Assistant")
class SteamHotSalesPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 设置字体路径，需要替换为实际的字体文件路径
        self.font_path = "app/plugins/SteamHotSales/fonts/msyh.ttc"  # 微软雅黑字体
        self.ensure_font_exists()

    def ensure_font_exists(self):
        """确保字体文件存在"""
        font_dir = "app/plugins/SteamHotSales/fonts"
        if not os.path.exists(font_dir):
            os.makedirs(font_dir)
        if not os.path.exists(self.font_path):
            self.ap.logger.error("字体文件不存在，请确保字体文件路径正确")

    def get_steam_top_sellers(self):
        api_url = "https://store.steampowered.com/api/featuredcategories"
        params = {
            "l": "schinese",  # 中文结果
            "cc": "CN"        # 中国区
        }

        try:
            response = requests.get(api_url, params=params)
            if response.status_code == 200:
                data = response.json()
                top_sellers = data.get("top_sellers", {}).get("items", [])
                
                games_info = []
                for game in top_sellers[:10]:
                    app_id = game["id"]
                    detail_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=CN&l=schinese"
                    detail_response = requests.get(detail_url)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        if detail_data[str(app_id)]["success"]:
                            game_data = detail_data[str(app_id)]["data"]
                            
                            price_info = game_data.get("price_overview", {})
                            if price_info:
                                original_price = price_info.get("initial_formatted", "")
                                final_price = price_info.get("final_formatted", "")
                                discount = price_info.get("discount_percent", 0)
                            else:
                                original_price = "免费游戏"
                                final_price = "免费"
                                discount = 0

                            game_info = {
                                "name": game_data.get("name", "未知"),
                                "original_price": original_price,
                                "final_price": final_price,
                                "discount": discount,
                                "header_image": game_data.get("header_image", ""),
                                "release_date": game_data.get("release_date", {}).get("date", "发布日期未知"),
                                "developers": ", ".join(game_data.get("developers", ["开发商未知"])),
                                "description": game_data.get("short_description", "暂无描述")
                            }
                            games_info.append(game_info)
                
                return games_info
            else:
                self.ap.logger.error(f"获取热销榜信息失败，状态码：{response.status_code}")
                return None
        except Exception as e:
            self.ap.logger.error(f"发生错误: {e}")
            return None



    def download_image(self, url):
        """下载图片"""
        try:
            response = requests.get(url)
            return Image.open(BytesIO(response.content))
        except Exception as e:
            self.ap.logger.error(f"下载图片失败: {e}")
            return None

    def create_game_image(self, games_info):
        """创建游戏信息图片"""
        if not games_info:
            return None

        # 设置图片尺寸和样式
        width = 1200
        height = 250 * len(games_info) + 150  # 每个游戏250像素高度，顶部预留150像素
        background_color = (27, 40, 56)  # Steam风格深蓝色背景
        text_color = (255, 255, 255)  # 白色文字

        # 创建图片和绘图对象
        image = Image.new('RGB', (width, height), background_color)
        draw = ImageDraw.Draw(image)

        # 加载字体
        title_font = ImageFont.truetype(self.font_path, 48)
        game_title_font = ImageFont.truetype(self.font_path, 36)
        info_font = ImageFont.truetype(self.font_path, 24)
        desc_font = ImageFont.truetype(self.font_path, 20)

        # 绘制标题
        title = "Steam 热销榜 Top 10"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((50, 30), title, font=title_font, fill=text_color)
        draw.text((50, 90), f"更新时间: {current_time}", font=info_font, fill=(180, 180, 180))

        y = 150
        for index, game in enumerate(games_info, 1):
            # 下载并调整游戏封面图片大小
            game_image = self.download_image(game['header_image'])
            if game_image:
                game_image = game_image.resize((300, 140), Image.Resampling.LANCZOS)
                image.paste(game_image, (50, y))

            # 绘制游戏标题
            draw.text((380, y), f"{index}. {game['name']}", font=game_title_font, fill=text_color)

            # 绘制价格信息
            price_y = y + 50
            if game['discount'] > 0:
                discount_text = f"-{game['discount']}%"
                draw.text((380, price_y), game['original_price'], font=info_font, fill=(128, 128, 128))
                draw.text((500, price_y), discount_text, font=info_font, fill=(0, 255, 0))
                draw.text((600, price_y), game['final_price'], font=info_font, fill=(0, 255, 0))
            else:
                draw.text((380, price_y), game['final_price'], font=info_font, fill=text_color)

            # 绘制发布日期和开发商
            draw.text((380, price_y + 30), f"发布日期: {game['release_date']}", font=info_font, fill=(180, 180, 180))
            draw.text((380, price_y + 60), f"开发商: {game['developers']}", font=info_font, fill=(180, 180, 180))

            # 绘制游戏描述（自动换行）
            desc_wrapped = textwrap.fill(game['description'], width=50)
            draw.text((380, price_y + 90), desc_wrapped, font=desc_font, fill=(150, 150, 150))

            # 分隔线
            draw.line([(50, y + 230), (width - 50, y + 230)], fill=(60, 70, 80), width=2)

            y += 250

        # 转换图片为字节流
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG', quality=95)
        img_byte_arr.seek(0)
        return img_byte_arr

    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message.lower()
        if msg in ["steam", "steam热销", "steam热销榜"]:
            self.ap.logger.debug(f"正在获取Steam热销榜 - 请求来自: {ctx.event.sender_id}")
            games_info = self.get_steam_top_sellers()
            if games_info:
                img_bytes = self.create_game_image(games_info)
                if img_bytes:
                    ctx.add_return("image", [img_bytes])
                else:
                    ctx.add_return("reply", ["生成图片失败，请稍后再试"])
            else:
                ctx.add_return("reply", ["获取Steam热销榜失败，请稍后再试"])
            ctx.prevent_default()

    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message.lower()
        if msg in ["steam", "steam热销", "steam热销榜"]:
            self.ap.logger.debug(f"正在获取Steam热销榜 - 请求来自群: {ctx.event.group_id}")
            games_info = self.get_steam_top_sellers()
            if games_info:
                img_bytes = self.create_game_image(games_info)
                if img_bytes:
                    ctx.add_return("image", [img_bytes])
                else:
                    ctx.add_return("reply", ["生成图片失败，请稍后再试"])
            else:
                ctx.add_return("reply", ["获取Steam热销榜失败，请稍后再试"])
            ctx.prevent_default()

    def __del__(self):
        pass
