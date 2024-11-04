# cogs/youtube_features.py
import discord
from discord.ext import commands
from discord import app_commands
from googleapiclient.discovery import build
import os
import re
from datetime import datetime, timedelta
import pytz
import asyncio
from typing import Optional, Dict, List, Tuple
import aiohttp
import json

class ChatMessage:
    def __init__(self, timestamp: datetime, author: str, message: str):
        self.timestamp = timestamp
        self.author = author
        self.message = message

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.author}: {self.message}"

class YouTubeFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.youtube = build('youtube', 'v3', 
                           developerKey=os.getenv('YOUTUBE_API_KEY'))
        
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',  # Regular video URLs
            r'youtu\.be\/([0-9A-Za-z_-]{11})',   # Shortened URLs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def get_stream_details(self, video_id: str) -> Optional[dict]:
        """Get details about the stream."""
        try:
            request = self.youtube.videos().list(
                part="snippet,liveStreamingDetails",
                id=video_id
            )
            response = request.execute()
            
            if not response['items']:
                print(f"No video found for ID: {video_id}")
                return None
                
            video = response['items'][0]
            details = video.get('liveStreamingDetails', {})
            
            print(f"Stream details for {video_id}:")
            print(f"Title: {video['snippet'].get('title', 'Unknown')}")
            print(f"LiveStreamingDetails: {json.dumps(details, indent=2)}")
            
            if not details:
                print("No livestreaming details found")
                return None
                
            return {
                'title': video['snippet'].get('title', 'Unknown Stream'),
                'start_time': details.get('actualStartTime'),
                'end_time': details.get('actualEndTime'),
                'is_live': details.get('actualEndTime') is None
            }
        except Exception as e:
            print(f"Error getting stream details: {e}")
            return None

    async def get_chat_replay(self, video_id: str, duration_minutes: int = 180) -> List[ChatMessage]:
        """Get chat replay for a completed stream using YouTube's archive format."""
        messages = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get video page to extract initial data
                initial_url = f"https://www.youtube.com/watch?v={video_id}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                
                async with session.get(initial_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Failed to get video page: {response.status}")
                        return messages
                        
                    html = await response.text()
                    
                    # Find the initial data
                    ytcfg_pattern = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
                    matches = re.finditer(ytcfg_pattern, html)
                    client_version = "2.20240201.01.00"
                    api_key = None
                    
                    for match in matches:
                        try:
                            cfg_data = json.loads(match.group(1))
                            if 'INNERTUBE_API_KEY' in cfg_data:
                                api_key = cfg_data['INNERTUBE_API_KEY']
                            if 'INNERTUBE_CLIENT_VERSION' in cfg_data:
                                client_version = cfg_data['INNERTUBE_CLIENT_VERSION']
                        except json.JSONDecodeError:
                            continue
                    
                    if not api_key:
                        print("Could not find API key")
                        return messages
                    
                    # Get the chat continuation token
                    initial_data_pattern = r'window\["ytInitialData"\]\s*=\s*({.+?});'
                    data_match = re.search(initial_data_pattern, html)
                    if not data_match:
                        print("Could not find initial data")
                        return messages
                        
                    try:
                        initial_data = json.loads(data_match.group(1))
                        print("Found initial data, searching for transcript info...")
                        
                        # Try to find the transcript continuation token
                        transcript_renderer = None
                        try:
                            tabs = initial_data['engagementPanels']
                            for tab in tabs:
                                if 'engagementPanelSectionListRenderer' in tab:
                                    content = tab['engagementPanelSectionListRenderer'].get('content', {})
                                    if 'continuationItemRenderer' in content:
                                        transcript_renderer = content['continuationItemRenderer']
                                        break
                        except Exception as e:
                            print(f"Error finding transcript renderer: {e}")
                            return messages
                        
                        if not transcript_renderer:
                            print("Could not find transcript renderer")
                            return messages
                            
                        continuation_token = transcript_renderer['continuationEndpoint']['continuationCommand']['token']
                        print(f"Found continuation token: {continuation_token}")
                        
                        # Now get the actual chat data
                        chat_url = f"https://www.youtube.com/youtubei/v1/get_transcript?key={api_key}"
                        request_data = {
                            "context": {
                                "client": {
                                    "clientName": "DESKTOP",
                                    "clientVersion": client_version,
                                    "hl": "en",
                                    "gl": "US",
                                },
                            },
                            "params": continuation_token
                        }
                        
                        async with session.post(chat_url, json=request_data, headers=headers) as chat_response:
                            if chat_response.status != 200:
                                print(f"Failed to get chat data: {chat_response.status}")
                                return messages
                                
                            chat_data = await chat_response.json()
                            print(f"Got chat data response. Processing...")
                            
                            try:
                                actions = chat_data['actions']
                                for action in actions:
                                    if 'addChatItemAction' not in action:
                                        continue
                                        
                                    item = action['addChatItemAction']['item']
                                    if 'liveChatTextMessageRenderer' not in item:
                                        continue
                                        
                                    renderer = item['liveChatTextMessageRenderer']
                                    author = renderer.get('authorName', {}).get('simpleText', 'Unknown')
                                    
                                    # Get message text
                                    message_runs = renderer.get('message', {}).get('runs', [])
                                    message_text = ' '.join(run.get('text', '') for run in message_runs if 'text' in run)
                                    
                                    # Get timestamp
                                    timestamp_usec = int(renderer.get('timestampUsec', 0)) // 1000
                                    msg_time = datetime.fromtimestamp(timestamp_usec / 1000000, pytz.UTC)
                                    
                                    messages.append(ChatMessage(msg_time, author, message_text))
                                    
                                print(f"Processed {len(messages)} messages")
                                
                            except Exception as e:
                                print(f"Error processing chat data: {e}")
                                print(f"Chat data structure: {json.dumps(chat_data, indent=2)}")
                                return messages
                                
                    except json.JSONDecodeError as e:
                        print(f"Error parsing initial data: {e}")
                        return messages
                        
        except Exception as e:
            print(f"Error getting chat replay: {e}")
            print(f"Full error: {str(e)}")
            
        return sorted(messages, key=lambda x: x.timestamp)

    def save_transcript(self, messages: List[ChatMessage], video_id: str, stream_details: dict) -> str:
        """Save chat messages to a transcript file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_{video_id}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"YouTube Livestream Chat Transcript\n")
            f.write(f"Stream Title: {stream_details['title']}\n")
            f.write(f"Video ID: {video_id}\n")
            f.write(f"Stream Start: {stream_details.get('start_time', 'Unknown')}\n")
            f.write(f"Stream End: {stream_details.get('end_time', 'Unknown')}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 80 + "\n\n")
            
            for msg in messages:
                f.write(f"{str(msg)}\n")
                
        return filename

    @app_commands.command(
        name="generate-transcript",
        description="Generate a chat transcript from a YouTube livestream"
    )
    async def generate_transcript(
        self, 
        interaction: discord.Interaction, 
        url: str,
        duration_minutes: Optional[int] = 180
    ):
        await interaction.response.defer()
        
        video_id = self.extract_video_id(url)
        if not video_id:
            await interaction.followup.send(
                "❌ Invalid YouTube URL. Please provide a valid YouTube video URL.",
                ephemeral=True
            )
            return

        try:
            stream_details = await self.get_stream_details(video_id)
            if not stream_details:
                await interaction.followup.send(
                    "❌ This doesn't appear to be a livestream URL.",
                    ephemeral=True
                )
                return
                
            await interaction.followup.send(
                "📝 Collecting chat messages... This may take a few minutes.",
                ephemeral=True
            )
            
            messages = await self.get_chat_replay(video_id, duration_minutes)
            
            if not messages:
                await interaction.followup.send(
                    "❌ No chat messages found in the stream. The stream might be too old or chat replay might be disabled.",
                    ephemeral=True
                )
                return
                
            filename = self.save_transcript(messages, video_id, stream_details)
            
            # Create embed with information
            embed = discord.Embed(
                title="📝 Chat Transcript Generated",
                description=f"Stream: {stream_details['title']}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Messages Retrieved",
                value=f"{len(messages):,}",
                inline=True
            )
            
            embed.add_field(
                name="Time Range",
                value=f"From: {messages[0].timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                      f"To: {messages[-1].timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False
            )
            
            # Send the transcript file
            with open(filename, 'rb') as f:
                file = discord.File(f, filename=filename)
                await interaction.followup.send(
                    embed=embed,
                    file=file
                )
                
            # Clean up the file
            os.remove(filename)
            
        except Exception as e:
            print(f"Error generating transcript: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the transcript. "
                "Please try again later or contact the bot owner.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(YouTubeFeatures(bot))