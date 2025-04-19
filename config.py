# config.py
from dataclasses import dataclass
from typing import Optional
import json
import os

@dataclass
class BotConfig:
    event_notification_channel_id: Optional[int] = None
    event_notification_role_id: Optional[int] = None
    daily_summary_channel_id: Optional[int] = None
    daily_summary_role_id: Optional[int] = None
    daily_summary_time: str = "09:00"  # 24-hour format
    daily_summary_enabled: bool = True

    # YouTube Vertical Live Stream Monitor Settings
    youtube_monitor_enabled: bool = False
    youtube_channel_id: Optional[str] = None # The ID of the YouTube channel to monitor
    youtube_monitor_discord_channel_id: Optional[int] = None # Discord channel ID for announcements
    youtube_monitor_check_interval_minutes: int = 5 # How often to check YouTube (in minutes)
    youtube_monitor_platform_links: dict[str, str] = None # Dict of platform names to URLs (e.g., {"Twitch": "...", "Kick": "..."})
    youtube_monitor_announcement_message: str = "{streamer_name} is now live with a vertical stream! Watch here: {stream_url}\n{other_links}" # Announcement message template

    @classmethod
    def load(cls) -> 'BotConfig':
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r') as f:
                    data = f.read()
                    if data.strip():  # Check if file is not empty
                        loaded_data = json.loads(data)

                        # Get defined fields from the dataclass
                        defined_fields = {f.name for f in cls.__dataclass_fields__.values()}

                        # Filter loaded data to only include defined fields
                        filtered_data = {k: v for k, v in loaded_data.items() if k in defined_fields}

                        # Initialize with filtered data
                        config_instance = cls(**filtered_data)

                        # Ensure new fields have defaults if missing in filtered data (or handle specific types)
                        if getattr(config_instance, 'youtube_monitor_platform_links', None) is None:
                            config_instance.youtube_monitor_platform_links = {} # Ensure it's a dict

                        # Check if any unexpected keys were ignored and log if desired
                        ignored_keys = set(loaded_data.keys()) - defined_fields
                        if ignored_keys:
                            print(f"Warning: Ignored unexpected keys found in config.json: {', '.join(ignored_keys)}")

                        return config_instance
            except (json.JSONDecodeError, TypeError, KeyError, AttributeError) as e:
                # More specific error logging might be helpful here
                print(f"Warning: Error processing config.json ({type(e).__name__}: {e}), creating/updating configuration")

        # If file doesn't exist, is invalid, or missing keys, create/update config
        config = cls()
        # If loaded_data exists from a partial load attempt, update defaults
        if 'loaded_data' in locals():
             for key, value in loaded_data.items():
                 if hasattr(config, key):
                     setattr(config, key, value)
        # Ensure platform links is a dict if loaded as None
        if config.youtube_monitor_platform_links is None:
             config.youtube_monitor_platform_links = {}
        config.save()
        return config
    
    def save(self):
        with open('config.json', 'w') as f:
            json.dump(self.__dict__, f, indent=2)
