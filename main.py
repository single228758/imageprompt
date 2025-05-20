import os
import tomllib
import base64
import time
import traceback
import asyncio
import imghdr
import xml.etree.ElementTree as ET

import aiohttp
from loguru import logger

from WechatAPI import WechatAPIClient
from utils.decorators import on_text_message, on_image_message
from utils.plugin_base import PluginBase

class ImagePromptPlugin(PluginBase):
    description = "简单获取反推图片提示词插件，/反推，获取中文提示词"
    author = "xxxbot团伙"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self.user_states = {}
        self.session = None # Initialize session to None
        config_path = os.path.join(os.path.dirname(__file__), "config.toml")
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            
            basic_config = config.get("basic", {})
            self.enable = basic_config.get("enable", True)
            self.trigger_word_zh = basic_config.get("trigger_word_zh", "/反推")
            self.trigger_word_en = basic_config.get("trigger_word_en", "/反推 英文")
            self.api_url = basic_config.get("api_url", "https://imageprompt.org/api/ai/prompts/image")
            self.user_state_timeout = basic_config.get("user_state_timeout", 300)
            self.default_image_model_id = basic_config.get("default_image_model_id", 0)

            self.headers = {
                'Content-Type': 'application/json',
                'Accept': '*/*',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'Origin': 'https://imageprompt.org',
                'Referer': 'https://imageprompt.org/'
            }
            logger.info(f"[ImagePrompt] Plugin loaded. Trigger ZH: '{self.trigger_word_zh}', Trigger EN: '{self.trigger_word_en}'")

        except FileNotFoundError:
            logger.error(f"[ImagePrompt] config.toml not found at {config_path}. Disabling plugin.")
            self.enable = False
        except Exception as e:
            logger.error(f"[ImagePrompt] Error loading config.toml: {e}. Disabling plugin.")
            logger.debug(traceback.format_exc())
            self.enable = False

    async def async_init(self):
        """Perform async initialization."""
        if self.enable:
            self.session = aiohttp.ClientSession()
            logger.info("[ImagePrompt] aiohttp.ClientSession initialized.")

    async def on_disable(self):
        """Plugin disabled, clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("[ImagePrompt] aiohttp.ClientSession closed.")
        logger.info("[ImagePrompt] Plugin disabled.")

    @on_text_message(priority=60)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable or not self.session:
            return True

        content = message.get("Content", "").strip()
        from_user_id = message.get("FromWxid")

        if not from_user_id:
            logger.warning("[ImagePrompt] Could not get FromWxid from message.")
            return True

        # Clean up expired states
        for user_id, state_data in list(self.user_states.items()):
            if time.time() - state_data.get("timestamp", 0) > self.user_state_timeout:
                logger.info(f"[ImagePrompt] State for user {user_id} expired. Action: {state_data.get('action')}")
                del self.user_states[user_id]
        
        prompt_lang = None
        reply_message = ""

        if content == self.trigger_word_zh:
            prompt_lang = "zh"
            reply_message = "请发送需要反推提示词的图片。"
        elif content == self.trigger_word_en:
            prompt_lang = "en"
            reply_message = "Please send the image for which you want to generate a prompt."

        if prompt_lang:
            self.user_states[from_user_id] = {
                "action": "waiting_image",
                "language": prompt_lang,
                "timestamp": time.time()
            }
            logger.info(f"[ImagePrompt] User {from_user_id} triggered with lang '{prompt_lang}'. Waiting for image.")
            await bot.send_text_message(from_user_id, reply_message)
            return False
        
        return True

    async def _get_image_bytes(self, bot: WechatAPIClient, message: dict) -> bytes | None:
        logger.debug(f"[ImagePrompt] Attempting to get image bytes for message: {message.get('MsgId')}")
        content_value = message.get('Content')
        from_user_id = message.get("FromWxid") # Get FromWxid for potential error messages
        msg_id = message.get("MsgId")

        # 1. Try to get Base64 directly from message content
        if isinstance(content_value, str) and len(content_value) > 200: # Arbitrary length check
            logger.debug(f"[ImagePrompt] Message Content length: {len(content_value)}. Trying Base64 direct decode.")
            try:
                base64_str_to_decode = content_value
                if "base64," in content_value:
                    base64_str_to_decode = content_value.split("base64,", 1)[1]
                
                decoded_bytes = base64.b64decode(base64_str_to_decode)
                # Basic validation: is it actually an image?
                if imghdr.what(None, h=decoded_bytes) is not None:
                    logger.info(f"[ImagePrompt] Successfully decoded Base64 image from message Content. Size: {len(decoded_bytes)} bytes.")
                    return decoded_bytes
                else:
                    logger.debug("[ImagePrompt] Decoded Base64 from Content, but not a recognized image format.")
            except (base64.binascii.Error, ValueError) as e:
                logger.debug(f"[ImagePrompt] Failed to decode Base64 from message Content: {e}. It might be XML or other data.")
            except Exception as e_direct_extract:
                logger.warning(f"[ImagePrompt] General error during direct Base64 extraction from Content: {e_direct_extract}")
                logger.debug(traceback.format_exc())
        
        # 2. Fallback to parsing XML and downloading using bot methods (inspired by Doubao)
        if not msg_id:
            logger.error("[ImagePrompt] Cannot download image: MsgId is missing and no direct Base64 found.")
            # Message to user will be handled by the final fallback or already sent by Base64 failure if that was the case
            return None

        logger.info(f"[ImagePrompt] No direct Base64 image found. Attempting download via MsgId: {msg_id}.")
        
        xml_content_str = content_value # Assume content_value holds the XML for image messages

        if not isinstance(xml_content_str, str) or not xml_content_str.strip().startswith("<msg>"):
            logger.warning(f"[ImagePrompt] Content for MsgId {msg_id} is not a valid XML string for image download. Content: {str(xml_content_str)[:200]}")
            # No user message here, final fallback will handle it.
            return None # Cannot proceed without XML

        try:
            tree = ET.fromstring(xml_content_str)
            img_element = tree.find("img")

            if img_element is not None:
                cdn_url = img_element.get("cdnmidimgurl")  # Medium quality preferred
                if not cdn_url:
                    cdn_url = img_element.get("cdnbigimgurl")  # Original/Big quality
                if not cdn_url:
                    cdn_url = img_element.get("cdnthumburl")  # Thumbnail as last resort

                aes_key = img_element.get("aeskey")
                total_len_str = img_element.get("length")  # For big/mid image
                if not total_len_str:  # Fallback for thumb if others not found
                    total_len_str = img_element.get("cdnthumblength")
                
                total_len = None
                if total_len_str and total_len_str.isdigit():
                    total_len = int(total_len_str)

                if cdn_url and aes_key and total_len is not None:
                    logger.info(f"[ImagePrompt] XML parsed for MsgId {msg_id}. CDN URL: {cdn_url}, AES Key: present, Total Length: {total_len}")
                    
                    image_data = None
                    if hasattr(bot, 'download_file_from_cdn'):
                        logger.info(f"[ImagePrompt] Attempting download via bot.download_file_from_cdn for MsgId: {msg_id}")
                        try:
                            image_data = await bot.download_file_from_cdn(
                                cdn_url=cdn_url,
                                aes_key=aes_key,
                                file_size=total_len,
                                file_type="image",
                                msg_id=msg_id
                            )
                        except Exception as e_cdn_specific:
                            logger.error(f"[ImagePrompt] bot.download_file_from_cdn failed for {msg_id}: {e_cdn_specific}")
                            logger.debug(traceback.format_exc())
                    elif hasattr(bot, 'download_file'):
                        logger.info(f"[ImagePrompt] Attempting download via generic bot.download_file for MsgId: {msg_id}. This method might need to handle XML itself.")
                        try:
                            # Assuming download_file(msg_id) can handle it, or it might take cdn_url etc.
                            # This is a less preferred path if download_file_from_cdn exists.
                            image_data = await bot.download_file(msg_id=msg_id) 
                        except Exception as e_cdn_generic:
                            logger.error(f"[ImagePrompt] bot.download_file failed for {msg_id}: {e_cdn_generic}")
                            logger.debug(traceback.format_exc())
                    else:
                        logger.error(f"[ImagePrompt] No suitable download method (download_file_from_cdn or download_file) found in WechatAPIClient for MsgId: {msg_id}.")

                    if image_data:
                        logger.info(f"[ImagePrompt] Successfully downloaded image via CDN/bot_method for MsgId {msg_id}. Size: {len(image_data)} bytes.")
                        return image_data
                    else:
                        logger.error(f"[ImagePrompt] Failed to download image via CDN/bot_method for MsgId {msg_id} using parsed XML.")
                else:
                    logger.warning(f"[ImagePrompt] Incomplete CDN info in XML for MsgId {msg_id}. URL: {cdn_url}, Key: {bool(aes_key)}, Len: {total_len}")
            else:
                logger.warning(f"[ImagePrompt] No <img> tag found in XML content for MsgId {msg_id}.")

        except ET.ParseError as e_xml:
            logger.error(f"[ImagePrompt] XML ParseError for MsgId {msg_id}: {e_xml}. Content: {str(xml_content_str)[:200]}")
        except Exception as e_download:
            logger.error(f"[ImagePrompt] Error during XML parsing or CDN download for MsgId {msg_id}: {e_download}")
            logger.debug(traceback.format_exc())
        
        # Final fallback or error message if all attempts failed
        logger.warning(f"[ImagePrompt] All methods to get image bytes failed for MsgId {msg_id or 'Unknown'}.")
        if from_user_id:
            # Check if a more specific error message was already sent by one of the download attempts.
            # This is a simple check; more sophisticated state tracking could be used.
            # For now, if any error occurred and we reached here, send a generic failure message.
            await bot.send_text_message(from_user_id, "抱歉，无法获取您发送的图片数据。请尝试其他图片或联系管理员。")
        return None

    @on_image_message(priority=60)
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        if not self.enable or not self.session:
            return True

        from_user_id = message.get("FromWxid")
        if not from_user_id:
            logger.warning("[ImagePrompt] Could not get FromWxid from image message.")
            return True

        user_state = self.user_states.get(from_user_id)

        if not user_state or user_state.get("action") != "waiting_image":
            logger.debug(f"[ImagePrompt] Received image from {from_user_id}, but not in waiting_image state or no state found.")
            return True # Not waiting for an image from this user for this action

        if time.time() - user_state.get("timestamp", 0) > self.user_state_timeout:
            logger.info(f"[ImagePrompt] State for user {from_user_id} (waiting_image) has expired.")
            await bot.send_text_message(from_user_id, "您发送图片超时了，请重新使用命令。")
            del self.user_states[from_user_id]
            return False # Consume the image, but don't process

        logger.info(f"[ImagePrompt] Received image from {from_user_id} who is in waiting_image state.")
        
        try:
            await bot.send_text_message(from_user_id, "图片已收到，正在反推提示词，请稍候...")
            image_bytes = await self._get_image_bytes(bot, message)

            if not image_bytes:
                logger.error(f"[ImagePrompt] Failed to get image bytes for user {from_user_id}.")
                # Error message sent by _get_image_bytes if specific download fails
                # await bot.send_text_message(from_user_id, "无法处理您发送的图片，请重试。")
                return False # Consume, error handled

            image_type = imghdr.what(None, h=image_bytes)
            if not image_type: # Fallback if imghdr can't determine
                logger.warning("[ImagePrompt] Could not determine image type using imghdr. Defaulting to jpeg.")
                image_type = "jpeg"
            
            encoded_image_string = base64.b64encode(image_bytes).decode('utf-8')
            base64_url = f"data:image/{image_type};base64,{encoded_image_string}"
            
            language = user_state.get("language", "zh")
            payload = {
                "base64Url": base64_url,
                "imageModelId": self.default_image_model_id,
                "language": language
            }

            logger.debug(f"[ImagePrompt] Sending API request to {self.api_url} for user {from_user_id}. Lang: {language}. Image size: {len(image_bytes)}")

            async with self.session.post(self.api_url, json=payload, headers=self.headers, timeout=60) as response:
                if response.status == 200:
                    response_json = await response.json()
                    prompt = response_json.get("prompt")
                    if prompt:
                        logger.info(f"[ImagePrompt] Successfully got prompt for user {from_user_id}: {prompt[:100]}...")
                        await bot.send_text_message(from_user_id, f"反推的提示词 ({language}):\n{prompt}")
                    else:
                        logger.error(f"[ImagePrompt] API success but no prompt in response for {from_user_id}. Response: {response_json}")
                        await bot.send_text_message(from_user_id, "抱歉，未能从图片生成提示词，API返回数据格式有误。")
                else:
                    error_text = await response.text()
                    logger.error(f"[ImagePrompt] API request failed for user {from_user_id}. Status: {response.status}. Response: {error_text[:200]}")
                    await bot.send_text_message(from_user_id, f"抱歉，生成提示词失败 (API错误 {response.status})。请稍后再试。")
        
        except aiohttp.ClientConnectorError as e:
            logger.error(f"[ImagePrompt] Network connection error for {from_user_id}: {e}")
            await bot.send_text_message(from_user_id, "抱歉，连接图像处理服务失败，请检查网络或稍后再试。")
        except asyncio.TimeoutError:
            logger.error(f"[ImagePrompt] API request timeout for user {from_user_id}.")
            await bot.send_text_message(from_user_id, "抱歉，请求超时，图像处理服务可能正忙，请稍后再试。")
        except Exception as e:
            logger.error(f"[ImagePrompt] Error processing image for user {from_user_id}: {e}")
            logger.debug(traceback.format_exc())
            await bot.send_text_message(from_user_id, "处理图片时发生未知错误，请联系管理员。")
        finally:
            if from_user_id in self.user_states:
                logger.debug(f"[ImagePrompt] Clearing state for user {from_user_id} after processing.")
                del self.user_states[from_user_id]
        
        return False # Consumed the image message
