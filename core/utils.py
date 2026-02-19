# core/utils.py
from datetime import datetime

def parse_timestamp(timestamp_str):
    """Parse ISO timestamp string to datetime object"""
    if not timestamp_str:
        return None
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

def parse_supabase_data(data, *timestamp_fields):
    """Parse timestamp fields in Supabase response data"""
    if isinstance(data, list):
        return [parse_supabase_data(item, *timestamp_fields) for item in data]
    
    if isinstance(data, dict):
        for field in timestamp_fields:
            if data.get(field):
                data[field] = parse_timestamp(data[field])
    
    return data