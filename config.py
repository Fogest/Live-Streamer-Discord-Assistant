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
    calendar_check_interval: int = 5  # minutes
    google_calendar_id: str = ""
    
    @classmethod
    def load(cls) -> 'BotConfig':
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r') as f:
                    data = f.read()
                    if data.strip():  # Check if file is not empty
                        return cls(**json.loads(data))
            except (json.JSONDecodeError, TypeError):
                print("Warning: Invalid config.json found, creating new configuration")
        
        # If file doesn't exist or is invalid, create new config
        config = cls()
        config.save()
        return config
    
    def save(self):
        with open('config.json', 'w') as f:
            json.dump(self.__dict__, f, indent=2)